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
    //  KELTNER IMPULSE BOT - v2 (data collection)
    //  Strategia mean-reversion dopo impulso sul Keltner Channel.
    //  Obiettivo: raccogliere dati ONESTI per verificare l'edge, non massimizzare.
    //
    //  IMPORTANTE per il backtest:
    //   - dati: "m1 bars from server" (tick se disponibili)
    //   - spread fisso realistico (XAUUSD ~25 pip) + commissione del conto vero
    //   - capitale iniziale e valuta (1000 EUR) si impostano nella finestra di backtest
    //   - setup stabilizzato consigliato: Min SL = 500 pips, Rischio = 1%, guard 50%
    // ============================================================================
    [Robot(AccessRights = AccessRights.FullAccess, TimeZone = TimeZones.UTC)]
    public class KeltnerImpulseBot : Robot
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

        // ATR smoothing: WilderSmoothing (RMA) = default del Keltner di TradingView, per confronto 1:1.
        // Esposto come parametro -> e' un asse di ROBUSTEZZA da testare, non da ottimizzare.
        [Parameter("ATR smoothing", Group = "Keltner", DefaultValue = MovingAverageType.WilderSmoothing)]
        public MovingAverageType AtrMaType { get; set; }

        // ---------------- Parametri strategia ----------------
        [Parameter("Target % impulso (TP)", Group = "Strategia", DefaultValue = 80.0, MinValue = 1.0)]
        public double ImpulseTargetPercent { get; set; }

        [Parameter("Risk/Reward (TP = RR * SL)", Group = "Strategia", DefaultValue = 1.2, MinValue = 0.1)]
        public double RiskReward { get; set; }

        [Parameter("Scadenza ordine (candele)", Group = "Strategia", DefaultValue = 20, MinValue = 1)]
        public int ExpiryBars { get; set; }

        [Parameter("Min SL (pips, 0 = off)", Group = "Strategia", DefaultValue = 0.0, MinValue = 0.0)]
        public double MinStopPips { get; set; }

        // A/B test della logica di sostituzione dell'ordine pendente:
        //  false = logica NUOVA (spec utente): sostituisce solo se una candela CHIUDE oltre l'estremo dell'impulso
        //  true  = logica VECCHIA: sostituisce ad ogni candela che chiude fuori dal canale
        [Parameter("Sostituzione su chiusura fuori banda (vecchia logica)", Group = "Strategia", DefaultValue = false)]
        public bool ReplaceOnOutsideClose { get; set; }

        // ---------------- Gestione rischio ----------------
        [Parameter("Rischio % per trade", Group = "Rischio", DefaultValue = 2.0, MinValue = 0.01)]
        public double RiskPercent { get; set; }

        // Salvavita anti-rovina: se il balance scende sotto questa % del capitale iniziale,
        // il bot cancella il pendente e smette di aprire nuovi trade (0 = disattivato).
        [Parameter("Stop se balance < % iniziale (0=off)", Group = "Rischio", DefaultValue = 50.0, MinValue = 0.0)]
        public double EquityGuardPercent { get; set; }

        // ---------------- Logging ----------------
        [Parameter("Scrivi CSV", Group = "Log", DefaultValue = true)]
        public bool EnableCsv { get; set; }

        [Parameter("Cartella log", Group = "Log", DefaultValue = "C:\\cTraderData")]
        public string LogFolder { get; set; }

        // Disegno del canale + segni sulle candele che rompono. SOLO per test corti (pochi giorni):
        // su 3 anni genera milioni di oggetti grafici e rallenta/blocca tutto.
        [Parameter("Disegna Keltner sul grafico (SOLO test corti)", Group = "Log", DefaultValue = false)]
        public bool DrawChannel { get; set; }

        // ---------------- Stato interno ----------------
        private const string BotLabel = "KeltnerImpulse";

        private MovingAverage _ema;
        private AverageTrueRange _atr;

        private int _nextId = 1;
        private int _placedBarCount;               // per la scadenza dell'ordine pendente
        private bool _pendingIsLong;               // direzione del setup pendente
        private double _pendingExtreme;            // estremo (high long / low short) della candela d'impulso corrente
        private double _initialBalance;            // per il salvavita anti-rovina
        private bool _halted;                      // true = equity guard scattato, niente piu' trade

        // stato per il disegno del canale
        private double _prevUpper, _prevMid, _prevLower;
        private int _prevDrawIndex = -1;
        private readonly Dictionary<int, TradeInfo> _trades = new Dictionary<int, TradeInfo>();

        private string _tradesFile;
        private string _skipsFile;

        // contatori di sintesi
        private int _cntSignals, _cntPlaced, _cntReplaced, _cntExpired, _cntFilled, _cntSkipped;

        // ---------------------------------------------------------------------
        protected override void OnStart()
        {
            _ema = Indicators.MovingAverage(Bars.ClosePrices, EmaPeriod, MovingAverageType.Exponential);
            _atr = Indicators.AverageTrueRange(AtrPeriod, AtrMaType);
            _initialBalance = Account.Balance;

            Positions.Closed += OnPositionsClosed;
            PendingOrders.Filled += OnPendingOrderFilled;

            if (EnableCsv)
                InitCsv();

            Print("KeltnerImpulseBot avviato su {0} {1} | balance {2}", SymbolName, TimeFrame, Account.Balance);
        }

        protected override void OnStop()
        {
            // Flush di posizioni/ordini ancora aperti a fine run -> niente survivorship bias nel CSV.
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
                else
                {
                    LogSkip(t.Id, t.Direction, "PENDING_AT_STOP", "ordine pendente non eseguito a fine run");
                }
            }

            Print("RIEPILOGO -> segnali:{0} ordini:{1} sostituiti:{2} scaduti:{3} eseguiti:{4} scartati:{5}",
                _cntSignals, _cntPlaced, _cntReplaced, _cntExpired, _cntFilled, _cntSkipped);
        }

        private Position FindPositionById(int id)
        {
            foreach (var p in Positions)
                if (p.Label == BotLabel && p.SymbolName == SymbolName && ParseId(p.Comment) == id)
                    return p;
            return null;
        }

        // Disegna le tre linee del Keltner (banda sup, media, banda inf) come segmenti tra candele chiuse.
        private void DrawKeltner(double upper, double mid, double lower)
        {
            int idx = Bars.Count - 2;   // candela appena chiusa
            if (_prevDrawIndex >= 0 && idx > _prevDrawIndex)
            {
                Chart.DrawTrendLine("kU" + idx, _prevDrawIndex, _prevUpper, idx, upper, Color.Gold);
                Chart.DrawTrendLine("kM" + idx, _prevDrawIndex, _prevMid, idx, mid, Color.Gray);
                Chart.DrawTrendLine("kL" + idx, _prevDrawIndex, _prevLower, idx, lower, Color.Gold);
            }
            _prevUpper = upper;
            _prevMid = mid;
            _prevLower = lower;
            _prevDrawIndex = idx;
        }

        // ---------------------------------------------------------------------
        //  Logica principale: tutto su CANDELA CHIUSA (niente look-ahead)
        // ---------------------------------------------------------------------
        protected override void OnBar()
        {
            double middle = _ema.Result.Last(1);
            double atr = _atr.Result.Last(1);

            // warm-up indicatori
            if (double.IsNaN(middle) || double.IsNaN(atr) || atr <= 0)
                return;

            double close = Bars.ClosePrices.Last(1);
            double high = Bars.HighPrices.Last(1);
            double low = Bars.LowPrices.Last(1);
            double upper = middle + MultUp * atr;
            double lower = middle - MultDown * atr;

            if (DrawChannel)
                DrawKeltner(upper, middle, lower);

            var position = Positions.Find(BotLabel, SymbolName);
            var pending = FindOurPendingOrder();

            // Salvavita anti-rovina: sotto la soglia si chiude bottega (le posizioni aperte
            // finiscono da sole su SL/TP, ma niente nuovi ordini).
            if (_halted)
                return;
            if (EquityGuardPercent > 0 && Account.Balance < _initialBalance * EquityGuardPercent / 100.0)
            {
                _halted = true;
                if (pending != null)
                {
                    int gId = ParseId(pending.Comment);
                    CancelPendingOrder(pending);
                    _trades.Remove(gId);
                }
                LogSkip(0, "-", "EQUITY_GUARD",
                    string.Format("balance {0:F2} < {1:F0}% del capitale iniziale {2:F2}: bot fermato",
                        Account.Balance, EquityGuardPercent, _initialBalance));
                Print("EQUITY GUARD: balance {0:F2} sotto la soglia. Il bot smette di aprire trade.", Account.Balance);
                return;
            }

            // Una posizione per simbolo: se aperta, ignoro i segnali
            if (position != null)
                return;

            if (pending == null)
            {
                // CREAZIONE setup: solo su candela che CHIUDE fuori dal canale
                bool longSignal = close > upper;
                bool shortSignal = close < lower;
                if (longSignal || shortSignal)
                {
                    _cntSignals++;
                    PlaceSetup(longSignal, middle, high, low, null);
                }
                return;
            }

            // Ordine pendente presente: due modalita' di sostituzione (A/B test)
            if (ReplaceOnOutsideClose)
            {
                // VECCHIA logica: ogni candela che chiude fuori dal canale sostituisce l'ordine
                bool ls = close > upper;
                bool ss = close < lower;
                if (ls || ss)
                {
                    _cntSignals++;
                    PlaceSetup(ls, middle, high, low, pending);
                    return;
                }
            }
            else
            {
                // NUOVA logica (spec): sostituzione solo se la candela CHIUDE oltre l'estremo
                // della candela d'impulso. Conta la CHIUSURA (non il wick), non basta chiudere fuori banda.
                bool exceeded = _pendingIsLong ? (close > _pendingExtreme) : (close < _pendingExtreme);
                if (exceeded)
                {
                    PlaceSetup(_pendingIsLong, middle, high, low, pending);
                    return;
                }
            }

            // Scadenza dell'ordine pendente
            if ((Bars.Count - _placedBarCount) >= ExpiryBars)
            {
                int oldId = ParseId(pending.Comment);
                CancelPendingOrder(pending);
                _trades.Remove(oldId);
                _cntExpired++;
                LogSkip(oldId, pending.TradeType.ToString(), "EXPIRED",
                    string.Format("non eseguito entro {0} candele", ExpiryBars));
            }
        }

        // ---------------------------------------------------------------------
        // Crea (existing == null) o sostituisce (existing != null) il setup.
        // La sostituzione avviene solo quando una candela CHIUDE oltre l'estremo dell'impulso (gestito in OnBar).
        private void PlaceSetup(bool isLong, double middle, double high, double low, PendingOrder existing)
        {
            TradeType tt = isLong ? TradeType.Buy : TradeType.Sell;
            double extreme = isLong ? high : low;

            double impulse = Math.Abs(extreme - middle);
            double tpDist = (ImpulseTargetPercent / 100.0) * impulse;   // TP = 80% impulso
            double slDist = tpDist / RiskReward;                        // SL = TP / 1.2
            double entry = middle;                                      // limit sulla media

            double slPips = slDist / Symbol.PipSize;
            double tpPips = tpDist / Symbol.PipSize;

            // Guardia distanza minima SL (logga e salta, evita rifiuti silenziosi). Non tocca l'ordine esistente.
            // Con Min SL = 500 pips funge da FILTRO VOLATILITA'/COSTO (i trade piccoli perdono in tutti i regimi).
            if (MinStopPips > 0 && slPips < MinStopPips)
            {
                _cntSkipped++;
                LogSkip(_nextId, tt.ToString(), "MIN_SL",
                    string.Format("slPips={0:F1} < {1:F1}", slPips, MinStopPips));
                return;
            }

            // ---- Position sizing per rischio % ----
            double targetRisk = Account.Balance * RiskPercent / 100.0;
            double pipValue = Symbol.PipValue;                 // valore 1 pip per 1 unita', in valuta conto
            double riskPerUnit = slPips * pipValue;
            if (riskPerUnit <= 0)
                return;

            double rawVolume = targetRisk / riskPerUnit;
            double volume = Symbol.NormalizeVolumeInUnits(rawVolume, RoundingMode.Down);

            if (volume < Symbol.VolumeInUnitsMin)
            {
                _cntSkipped++;
                LogSkip(_nextId, tt.ToString(), "MIN_VOLUME",
                    string.Format("vol calcolato {0:F2} < min {1:F2} (rischio target troppo piccolo per il lotto minimo)",
                        rawVolume, Symbol.VolumeInUnitsMin));
                return;
            }
            if (volume > Symbol.VolumeInUnitsMax)
                volume = Symbol.VolumeInUnitsMax;

            double realRisk = slPips * pipValue * volume;

            // ---- Sostituzione dell'eventuale ordine pendente precedente ----
            if (existing != null)
            {
                int prevId = ParseId(existing.Comment);
                CancelPendingOrder(existing);
                _trades.Remove(prevId);
                _cntReplaced++;
                LogSkip(prevId, existing.TradeType.ToString(), "REPLACED", "candela chiude oltre l'impulso -> nuovo setup");
            }

            // ---- Piazzamento nuovo limit ----
            int id = _nextId++;
            var info = new TradeInfo
            {
                Id = id,
                Direction = isLong ? "LONG" : "SHORT",
                SignalTime = Server.Time,
                SignalClose = Bars.ClosePrices.Last(1),
                Middle = middle,
                Impulse = impulse,
                SlDist = slDist,
                TpDist = tpDist,
                SlPips = slPips,
                TpPips = tpPips,
                EntryPlanned = entry,
                RawVolume = rawVolume,
                Volume = volume,
                TheoRisk = targetRisk,
                RealRisk = realRisk
            };

            var result = PlaceLimitOrder(tt, SymbolName, volume, entry, BotLabel, slPips, tpPips, null, id.ToString());

            if (result.IsSuccessful)
            {
                _trades[id] = info;
                _placedBarCount = Bars.Count;   // il contatore di scadenza riparte ad ogni nuovo ordine
                _pendingIsLong = isLong;
                _pendingExtreme = extreme;      // nuovo riferimento: si sostituisce solo su CHIUSURA oltre questo livello
                _cntPlaced++;

                // Segno grafico: STELLA arancione = sostituzione (chiusura oltre l'impulso); freccia = nuovo setup.
                if (DrawChannel)
                {
                    int sigIdx = Bars.Count - 2;
                    if (existing != null)
                        Chart.DrawIcon("kReBreak" + sigIdx, ChartIconType.Star, sigIdx, extreme, Color.Orange);
                    else
                        Chart.DrawIcon("kNew" + sigIdx, isLong ? ChartIconType.UpArrow : ChartIconType.DownArrow,
                            sigIdx, extreme, isLong ? Color.Lime : Color.Red);
                }
            }
            else
            {
                _cntSkipped++;
                LogSkip(id, tt.ToString(), "PLACE_FAILED", result.Error.ToString());
            }
        }

        // ---------------------------------------------------------------------
        private void OnPendingOrderFilled(PendingOrderFilledEventArgs args)
        {
            var pos = args.Position;
            if (pos.Label != BotLabel || pos.SymbolName != SymbolName)
                return;

            int id = ParseId(pos.Comment);
            if (!_trades.ContainsKey(id))
            {
                Print("ATTENZIONE fill non mappato (comment='{0}'): trade NON loggato. Verificare propagazione comment del broker.", pos.Comment);
                return;
            }

            var t = _trades[id];
            t.FillTime = Server.Time;
            t.EntryActual = pos.EntryPrice;
            t.FilledVolume = pos.VolumeInUnits;
            t.SpreadPipsAtFill = Symbol.Spread / Symbol.PipSize;
            t.RealRisk = t.SlPips * Symbol.PipValue * pos.VolumeInUnits;
            _cntFilled++;
        }

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
        }

        // ---------------------------------------------------------------------
        //  Helpers
        // ---------------------------------------------------------------------
        private PendingOrder FindOurPendingOrder()
        {
            foreach (var o in PendingOrders)
                if (o.Label == BotLabel && o.SymbolName == SymbolName)
                    return o;
            return null;
        }

        private static int ParseId(string comment)
        {
            int id;
            return int.TryParse(comment, out id) ? id : -1;
        }

        // ---------------------------------------------------------------------
        //  CSV
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
