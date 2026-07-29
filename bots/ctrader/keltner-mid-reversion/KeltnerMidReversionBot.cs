using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    // ============================================================================
    //  KELTNER MID-REVERSION BOT - v1 (data collection)
    //
    //  Stesso principio del Keltner, ma:
    //   - ENTRA SUBITO A MERCATO sulla prima candela che CHIUDE fuori dal canale
    //     (niente ordini limit, niente attesa del ritorno).
    //   - Direzione mean-reversion vera:
    //        close > banda superiore  -> SHORT (scommetto sul rientro verso la mid)
    //        close < banda inferiore  -> LONG
    //   - TAKE PROFIT sulla MID line (o "quasi" -> parametro Target % verso la mid).
    //
    //  Obiettivo: raccogliere dati ONESTI per verificare l'edge, non massimizzare.
    //
    //  IMPORTANTE per il backtest (come il bot Impulse):
    //   - usare "m1 bars from server" (il tick di FP non si scarica)
    //   - spread reale + commissione del conto vero
    //   - capitale iniziale e valuta (1000 EUR) si impostano nella finestra di backtest
    // ============================================================================
    [Robot(AccessRights = AccessRights.FullAccess, TimeZone = TimeZones.UTC)]
    public class KeltnerMidReversionBot : Robot
    {
        // ---------------- Parametri Keltner ----------------
        [Parameter("EMA Period (middle)", Group = "Keltner", DefaultValue = 20, MinValue = 1)]
        public int EmaPeriod { get; set; }

        [Parameter("ATR Period (bands)", Group = "Keltner", DefaultValue = 10, MinValue = 1)]
        public int AtrPeriod { get; set; }

        [Parameter("Mult banda superiore", Group = "Keltner", DefaultValue = 2.0, MinValue = 0.1)]
        public double MultUp { get; set; }

        [Parameter("Mult banda inferiore", Group = "Keltner", DefaultValue = 2.0, MinValue = 0.1)]
        public double MultDown { get; set; }

        [Parameter("ATR smoothing", Group = "Keltner", DefaultValue = MovingAverageType.Simple)]
        public MovingAverageType AtrMaType { get; set; }

        // ---------------- Parametri strategia ----------------
        // Quanto del tragitto "entrata -> mid" prendiamo come TP.
        // 100 = TP esattamente sulla mid. 90 = un po' prima della mid ("quasi"),
        // riempie piu' spesso. Esposto per testare la robustezza, non da ottimizzare.
        [Parameter("Target % verso la mid (TP)", Group = "Strategia", DefaultValue = 100.0, MinValue = 1.0, MaxValue = 100.0)]
        public double MidTargetPercent { get; set; }

        // Risk/Reward: SL_dist = TP_dist / RR.
        // Con RR = 1 lo stop e' distante quanto il TP (break-even win rate ~50% lordo).
        // RR < 1 -> SL piu' largo, serve win rate piu' alto. RR > 1 -> SL piu' stretto.
        [Parameter("Risk/Reward (TP = RR * SL)", Group = "Strategia", DefaultValue = 1.0, MinValue = 0.1)]
        public double RiskReward { get; set; }

        [Parameter("Min SL (pips, 0 = off)", Group = "Strategia", DefaultValue = 0.0, MinValue = 0.0)]
        public double MinStopPips { get; set; }

        // ---------------- Gestione rischio ----------------
        [Parameter("Rischio % per trade", Group = "Rischio", DefaultValue = 2.0, MinValue = 0.01)]
        public double RiskPercent { get; set; }

        // ---------------- Logging ----------------
        [Parameter("Scrivi CSV", Group = "Log", DefaultValue = true)]
        public bool EnableCsv { get; set; }

        [Parameter("Cartella log", Group = "Log", DefaultValue = "C:\\cTraderData\\midrev")]
        public string LogFolder { get; set; }

        // ---------------- Stato interno ----------------
        private const string BotLabel = "KeltnerMidRev";

        private MovingAverage _ema;
        private AverageTrueRange _atr;

        private int _nextId = 1;
        private readonly Dictionary<int, TradeInfo> _trades = new Dictionary<int, TradeInfo>();

        private string _tradesFile;
        private string _skipsFile;

        // contatori di sintesi
        private int _cntSignals, _cntOpened, _cntClosed, _cntSkipped;

        // ---------------------------------------------------------------------
        protected override void OnStart()
        {
            _ema = Indicators.MovingAverage(Bars.ClosePrices, EmaPeriod, MovingAverageType.Exponential);
            _atr = Indicators.AverageTrueRange(AtrPeriod, AtrMaType);

            Positions.Closed += OnPositionsClosed;

            if (EnableCsv)
                InitCsv();

            Print("KeltnerMidReversionBot avviato su {0} {1} | conto {2} {3}",
                SymbolName, TimeFrame, Account.Balance, Account.Currency);
        }

        protected override void OnStop()
        {
            // Flush delle posizioni ancora aperte a fine run -> niente survivorship bias nel CSV.
            foreach (var kv in _trades)
            {
                var t = kv.Value;
                var pos = FindPositionById(t.Id);
                if (pos != null)
                {
                    t.ExitTime = Server.Time;
                    t.GrossProfit = pos.GrossProfit;
                    t.Commission = pos.Commissions;
                    t.Swap = pos.Swap;
                    t.NetProfit = pos.NetProfit;
                    t.Pips = pos.Pips;
                    t.RMultiple = (t.RealRisk > 0) ? pos.NetProfit / t.RealRisk : 0.0;
                    t.CloseReason = "OPEN_AT_STOP";
                    WriteTradeRow(t);
                }
            }

            Print("RIEPILOGO -> segnali:{0} aperti:{1} chiusi:{2} scartati:{3}",
                _cntSignals, _cntOpened, _cntClosed, _cntSkipped);
        }

        private Position FindPositionById(int id)
        {
            foreach (var p in Positions)
                if (p.Label == BotLabel && p.SymbolName == SymbolName && ParseId(p.Comment) == id)
                    return p;
            return null;
        }

        // ---------------------------------------------------------------------
        //  Logica principale: tutto su CANDELA CHIUSA (niente look-ahead).
        //  L'entrata e' a MERCATO sulla candela appena chiusa fuori banda.
        // ---------------------------------------------------------------------
        protected override void OnBar()
        {
            double middle = _ema.Result.Last(1);
            double atr = _atr.Result.Last(1);

            // warm-up indicatori
            if (double.IsNaN(middle) || double.IsNaN(atr) || atr <= 0)
                return;

            double close = Bars.ClosePrices.Last(1);
            double upper = middle + MultUp * atr;
            double lower = middle - MultDown * atr;

            // Una posizione per simbolo: se aperta, ignoro i segnali (li conto solo).
            var position = Positions.Find(BotLabel, SymbolName);
            if (position != null)
            {
                if (close > upper || close < lower) _cntSignals++;
                return;
            }

            // Mean reversion: chiusura SOPRA la banda -> SHORT; SOTTO -> LONG.
            bool shortSignal = close > upper;
            bool longSignal = close < lower;

            if (longSignal || shortSignal)
            {
                _cntSignals++;
                HandleSignal(longSignal, middle, close);
            }
        }

        // ---------------------------------------------------------------------
        private void HandleSignal(bool isLong, double middle, double signalClose)
        {
            TradeType tt = isLong ? TradeType.Buy : TradeType.Sell;

            // Entriamo a mercato ~al close del segnale. Il TP punta alla mid.
            // Distanza fino alla mid = |close - middle| (e' il tragitto che vogliamo catturare).
            double distToMid = Math.Abs(signalClose - middle);
            double tpDist = (MidTargetPercent / 100.0) * distToMid;   // TP sulla mid (o "quasi")
            double slDist = tpDist / RiskReward;                      // SL = TP / RR (oltre la banda)

            double slPips = slDist / Symbol.PipSize;
            double tpPips = tpDist / Symbol.PipSize;

            // Guardia distanza minima SL (logga e salta, evita rifiuti silenziosi).
            if (MinStopPips > 0 && slPips < MinStopPips)
            {
                _cntSkipped++;
                LogSkip(_nextId, tt.ToString(), "MIN_SL",
                    string.Format("slPips={0:F1} < {1:F1}", slPips, MinStopPips));
                return;
            }

            // ---- Position sizing per rischio % ----
            double targetRisk = Account.Balance * RiskPercent / 100.0;
            double pipValue = Symbol.PipValue;
            double riskPerUnit = slPips * pipValue;
            if (riskPerUnit <= 0)
                return;

            double rawVolume = targetRisk / riskPerUnit;
            double volume = Symbol.NormalizeVolumeInUnits(rawVolume, RoundingMode.Down);

            if (volume < Symbol.VolumeInUnitsMin)
            {
                _cntSkipped++;
                LogSkip(_nextId, tt.ToString(), "MIN_VOLUME",
                    string.Format("vol calcolato {0:F2} < min {1:F2}", rawVolume, Symbol.VolumeInUnitsMin));
                return;
            }
            if (volume > Symbol.VolumeInUnitsMax)
                volume = Symbol.VolumeInUnitsMax;

            double realRisk = slPips * pipValue * volume;

            // ---- Entrata a MERCATO immediata ----
            int id = _nextId++;
            var info = new TradeInfo
            {
                Id = id,
                Direction = isLong ? "LONG" : "SHORT",
                SignalTime = Server.Time,
                SignalClose = signalClose,
                Middle = middle,
                Impulse = distToMid,
                SlDist = slDist,
                TpDist = tpDist,
                SlPips = slPips,
                TpPips = tpPips,
                EntryPlanned = signalClose,
                RawVolume = rawVolume,
                Volume = volume,
                TheoRisk = targetRisk,
                RealRisk = realRisk
            };

            var result = ExecuteMarketOrder(tt, SymbolName, volume, BotLabel, slPips, tpPips, id.ToString());

            if (result.IsSuccessful)
            {
                var pos = result.Position;
                info.FillTime = Server.Time;
                info.EntryActual = pos.EntryPrice;
                info.FilledVolume = pos.VolumeInUnits;
                info.SpreadPipsAtFill = Symbol.Spread / Symbol.PipSize;
                info.RealRisk = slPips * pipValue * pos.VolumeInUnits;
                _trades[id] = info;
                _cntOpened++;
            }
            else
            {
                _cntSkipped++;
                LogSkip(id, tt.ToString(), "OPEN_FAILED", result.Error.ToString());
            }
        }

        // ---------------------------------------------------------------------
        private void OnPositionsClosed(PositionClosedEventArgs args)
        {
            var pos = args.Position;
            if (pos.Label != BotLabel || pos.SymbolName != SymbolName)
                return;

            int id = ParseId(pos.Comment);
            if (!_trades.ContainsKey(id))
            {
                Print("ATTENZIONE chiusura non mappata (comment='{0}'): trade NON loggato.", pos.Comment);
                return;
            }

            var t = _trades[id];
            t.ExitTime = Server.Time;
            t.GrossProfit = pos.GrossProfit;
            t.Commission = pos.Commissions;
            t.Swap = pos.Swap;
            t.NetProfit = pos.NetProfit;
            t.Pips = pos.Pips;
            t.RMultiple = (t.RealRisk > 0) ? pos.NetProfit / t.RealRisk : 0.0;
            t.CloseReason = args.Reason.ToString();

            WriteTradeRow(t);
            _trades.Remove(id);
            _cntClosed++;
        }

        // ---------------------------------------------------------------------
        //  Helpers
        // ---------------------------------------------------------------------
        private static int ParseId(string comment)
        {
            int id;
            return int.TryParse(comment, out id) ? id : -1;
        }

        // ---------------------------------------------------------------------
        //  CSV (stesso header del bot Impulse -> riusa keltner_analyzer.py)
        // ---------------------------------------------------------------------
        private void InitCsv()
        {
            try
            {
                Directory.CreateDirectory(LogFolder);
                string tag = string.Format("{0}_{1}", SymbolName, TimeFrame);
                _tradesFile = Path.Combine(LogFolder, "trades_" + tag + ".csv");
                _skipsFile = Path.Combine(LogFolder, "skips_" + tag + ".csv");

                if (!System.IO.File.Exists(_tradesFile))
                    System.IO.File.AppendAllText(_tradesFile,
                        "id,signal_time_utc,fill_time_utc,exit_time_utc,min_signal_to_fill,direction," +
                        "signal_close,middle_entry,impulse,sl_dist,tp_dist,sl_pips,tp_pips," +
                        "entry_planned,entry_actual,spread_pips_fill,volume_units,raw_volume," +
                        "theo_risk,theo_risk_pct,real_risk,real_risk_pct,rounding_risk_delta," +
                        "gross_profit,commission,swap,net_profit,pips,R,close_reason\n");

                if (!System.IO.File.Exists(_skipsFile))
                    System.IO.File.AppendAllText(_skipsFile, "time_utc,id,direction,reason,detail\n");
            }
            catch (Exception ex)
            {
                Print("ERRORE creazione CSV: {0}", ex.Message);
                EnableCsv = false;
            }
        }

        private void WriteTradeRow(TradeInfo t)
        {
            if (!EnableCsv) return;
            try
            {
                var c = CultureInfo.InvariantCulture;
                double bal = Account.Balance;
                double minToFill = (t.FillTime - t.SignalTime).TotalMinutes;
                double theoRiskPct = bal > 0 ? t.TheoRisk / bal * 100.0 : 0;
                double realRiskPct = bal > 0 ? t.RealRisk / bal * 100.0 : 0;
                double roundingDelta = t.TheoRisk - t.RealRisk;

                string row = string.Join(",", new string[]
                {
                    t.Id.ToString(c),
                    t.SignalTime.ToString("yyyy-MM-dd HH:mm:ss", c),
                    t.FillTime.ToString("yyyy-MM-dd HH:mm:ss", c),
                    t.ExitTime.ToString("yyyy-MM-dd HH:mm:ss", c),
                    minToFill.ToString("F1", c),
                    t.Direction,
                    t.SignalClose.ToString("F5", c),
                    t.Middle.ToString("F5", c),
                    t.Impulse.ToString("F5", c),
                    t.SlDist.ToString("F5", c),
                    t.TpDist.ToString("F5", c),
                    t.SlPips.ToString("F1", c),
                    t.TpPips.ToString("F1", c),
                    t.EntryPlanned.ToString("F5", c),
                    t.EntryActual.ToString("F5", c),
                    t.SpreadPipsAtFill.ToString("F1", c),
                    t.FilledVolume.ToString("F2", c),
                    t.RawVolume.ToString("F2", c),
                    t.TheoRisk.ToString("F2", c),
                    theoRiskPct.ToString("F2", c),
                    t.RealRisk.ToString("F2", c),
                    realRiskPct.ToString("F2", c),
                    roundingDelta.ToString("F2", c),
                    t.GrossProfit.ToString("F2", c),
                    t.Commission.ToString("F2", c),
                    t.Swap.ToString("F2", c),
                    t.NetProfit.ToString("F2", c),
                    t.Pips.ToString("F1", c),
                    t.RMultiple.ToString("F3", c),
                    t.CloseReason
                });
                System.IO.File.AppendAllText(_tradesFile, row + "\n");
            }
            catch (Exception ex)
            {
                Print("ERRORE scrittura trade CSV: {0}", ex.Message);
            }
        }

        private void LogSkip(int id, string direction, string reason, string detail)
        {
            if (!EnableCsv) return;
            try
            {
                var c = CultureInfo.InvariantCulture;
                string row = string.Join(",", new string[]
                {
                    Server.Time.ToString("yyyy-MM-dd HH:mm:ss", c),
                    id.ToString(c),
                    direction,
                    reason,
                    "\"" + (detail ?? "").Replace("\"", "'") + "\""
                });
                System.IO.File.AppendAllText(_skipsFile, row + "\n");
            }
            catch { /* non bloccare il bot per un log */ }
        }

        // ---------------------------------------------------------------------
        private class TradeInfo
        {
            public int Id;
            public string Direction;
            public DateTime SignalTime, FillTime, ExitTime;
            public double SignalClose, Middle, Impulse;
            public double SlDist, TpDist, SlPips, TpPips;
            public double EntryPlanned, EntryActual, SpreadPipsAtFill;
            public double RawVolume, Volume, FilledVolume;
            public double TheoRisk, RealRisk;
            public double GrossProfit, Commission, Swap, NetProfit, Pips, RMultiple;
            public string CloseReason;
        }
    }
}
