// Сторінка «Рація» на клієнті.
//
// Малює те, що сказав сервер, і нічого не вирішує сама.
//
// НАЛАШТУВАННЯ ЧИСЛОМ, а не вибором зі списку. Іменовані канали були потрібні,
// поки частот було вісім; після зняття межі ефір міряється тисячами ділень, і
// список імен, яких ніхто не давав, показував би те, чого немає.
//
// Імена лишились, але тепер їх дає САМ ГРАВЕЦЬ. Книжка частот живе В ПАМ'ЯТІ
// ПРИЛАДУ (ТЗ-5 R-E5.1); носій -- спосіб її винести: записати на чип, забрати
// з чипа цілком або по одній (R-E5.4). Книжку можна передати разом із чипом, а
// прилад при цьому лишається домом: загубив чип -- книжка на місці (R-E5.7).
//
// Різниця з ручною рацією лишається одна, і вона ігрова: щоб перебудувати цю,
// треба ВІДКРИТИ КПК. На бігу не вийде.
//
// ВИБІР РЯДКА -- ЦЕ ВИДІЛЕННЯ, І ВОНО ЛИШАЄТЬСЯ (ТЗ-5 R-E1.1, рішення
// власника). Вибір заповнює поля частоти й імені; настроює окрема кнопка
// TUNE, забуває -- FORGET, і обидві працюють по виділеному. Раніше вибір
// настроював і тут же скидав виділення, тож FORGET діставав лише рядок поза
// досяжністю -- єдиний, який забувати безглуздо (R-E1.2, D97, D12).
//
// НАМІР І ПЛАТА -- ДВА РІЗНІ ЧИСЛА (рішення власника 2026-09-09).
//
// «+», «-» і вибір рядка книжки міняють ЛИШЕ намір -- те, що стоїть у полі
// ВСТАНОВИТИ ЧАСТОТУ. Плату рухає одна кнопка, НАЛАШТУВАТИ, і рухає вона на
// те, що в полі. На чому плата стоїть насправді, каже окремий рядок
// НАЛАШТОВАНО НА, і саме його -- і тільки його -- переписує щосекундна
// відповідь про стан.
//
// Раніше кожна з трьох дій слала настройку одразу, тож кнопка НАЛАШТУВАТИ не
// значила нічого, а поле жило рівно до наступної відповіді сервера: вибір
// рядка книжки видимо скидався назад на частоту плати. Причина -- не вибір, а
// те, що вибір писав своє ділення в m_FreqShown, тобто в пам'ять про
// СЕРВЕРНЕ число; найближчий Paint бачив розбіжність і чесно «виправляв» поле.

class OZR_PageRadio : OZ_PdaPage
{
    private EditBoxWidget     m_Freq;
    private EditBoxWidget     m_Name;
    private TextListboxWidget m_Book;
    private ButtonWidget      m_BtnTune;
    private ButtonWidget      m_BtnUp;
    private ButtonWidget      m_BtnDown;
    private ButtonWidget      m_BtnSave;
    private ButtonWidget      m_BtnForget;
    // Ряд носія: у режимі книжки -- «на чип» і «чип»; у режимі чипа --
    // «забрати», «усе» і «книжка».
    private ButtonWidget      m_BtnChipA;
    private ButtonWidget      m_BtnChipB;
    private ButtonWidget      m_BtnChipC;

    // Рядок, на який гравець НАЦІЛИВСЯ, і його ім'я: перемальовування списку
    // будує рядки наново, і виділення знаходиться знову за іменем, а не
    // губиться разом зі старим номером (D12).
    private int    m_Picked     = -1;
    private string m_PickedName = "";

    // НАМІР: ділення, яке сторінка запропонувала останньою дією гравця, або
    // -1, коли не пропонувала нічого. Поки це не -1, поле ВСТАНОВИТИ ЧАСТОТУ
    // належить ГРАВЦЕВІ, і оновлення стану в нього не лізе.
    //
    // Істина про намір -- сам текст поля: гравець міг набрати руками поверх
    // запропонованого. Це число лише каже, що поле вже не дзеркало плати.
    private int m_Pending = -1;

    // Ділення ПЛАТИ, яким ми його востаннє вписали в поле. Поле переписується
    // лише тоді, коли плата справді переїхала: Paint приходить на кожне
    // оновлення стану, і безумовний запис затирав би недонабране число.
    //
    // Сюди кладеться ТІЛЬКИ серверне число. Вибір рядка книжки писав сюди своє
    // -- і цим перетворював найближче оновлення стану на «виправлення» поля.
    private int m_FreqShown = -1;

    // Підпис пам'яті, за яким малювали книжку востаннє. Поки він не змінився,
    // перепитувати книжку нема сенсу: вона змінитись не могла.
    private bool m_StoresShown = false;
    private int  m_FreeShown   = -2;

    // Синхронізоване ділення, ЯКИМ МИ ЙОГО БАЧИЛИ МИНУЛОГО РАЗУ.
    //
    // Порівнювати клієнтське число з серверним НЕ МОЖНА: поки власна
    // синхрозмінна порожня, OZR_ShownIndex падає назад на рушій, а рушій на
    // клієнті відповідає за СВОЄЮ ванільною таблицею. Питання тут інше: чи
    // змінилось щось на предметі ВІДТОДІ, ЯК МИ МАЛЮВАЛИ.
    private int  m_SyncShown    = -2;

    // Коли стан востаннє не приїхав. Без цього відмова «немає приладу» чи
    // «не читається» лишала m_State порожнім, Drifted() відповідав «так»
    // щосекунди, і сторінка смикала сервер до самого закриття (D13).
    private int m_FailedAt = 0;
    private static const int RETRY_MS = 5000;

    // Режим носія: список показує книжку ЧИПА, а не приладу.
    private bool m_ChipMode = false;

    private ref OZR_RadioState m_State;

    // Книжка живе ОКРЕМО від стану, бо окремо й приїжджає. Своя копія ще й
    // переживає оновлення стану, тож виділення не стає недійсним щоразу, коли
    // сервер сказав про батарею.
    private ref OZR_BookList m_Rows;
    private ref OZR_BookList m_ChipRows;

    override string LayoutPath()
    {
        return "OpenZone_Radio_PDA/gui/layouts/ozr_page_radio.layout";
    }

    override void OnBuilt()
    {
        m_Freq      = EditBoxWidget.Cast(Wgt("FreqEdit"));
        m_Name      = EditBoxWidget.Cast(Wgt("NameEdit"));
        m_Book      = TextListboxWidget.Cast(Wgt("BookList"));
        m_BtnTune   = ButtonWidget.Cast(Wgt("BtnTune"));
        m_BtnUp     = ButtonWidget.Cast(Wgt("BtnUp"));
        m_BtnDown   = ButtonWidget.Cast(Wgt("BtnDown"));
        m_BtnSave   = ButtonWidget.Cast(Wgt("BtnSave"));
        m_BtnForget = ButtonWidget.Cast(Wgt("BtnForget"));
        m_BtnChipA  = ButtonWidget.Cast(Wgt("BtnChipA"));
        m_BtnChipB  = ButtonWidget.Cast(Wgt("BtnChipB"));
        m_BtnChipC  = ButtonWidget.Cast(Wgt("BtnChipC"));

        SetText("BtnTuneText",   "#STR_OZR_TUNE");
        SetText("BtnUpText",     "+");
        SetText("BtnDownText",   "-");
        SetText("BtnSaveText",   "#STR_OZR_SAVE");
        SetText("BtnForgetText", "#STR_OZR_FORGET");
        PaintButtons();
    }

    override void OnSelected()
    {
        // Зайшли наново -- і поле, і книжка заповнюються наново.
        m_Pending     = -1;
        m_FreqShown   = -1;
        m_FreeShown   = -2;
        m_SyncShown   = -2;
        m_StoresShown = false;
        m_FailedAt    = 0;
        m_Rows        = null;
        m_ChipRows    = null;
        m_ChipMode    = false;
        m_Picked      = -1;
        m_PickedName  = "";
        Ask();
        AskBook();
    }

    // СЕРВЕР НЕ ОПИТУЄТЬСЯ ПРОСТО ТАК: живлення КПК і ділення плати
    // синхронізовані на самому предметі, смуга за сесію не міняється.
    // Лишається один випадок: намальоване РОЗІЙШЛОСЯ з тим, що синхронізовано
    // (плату перебудували не з цієї сторінки). Тоді -- і тільки тоді -- питаємо.
    override void OnRefresh()
    {
        if (Drifted())
            Ask();
    }

    // КПК, який зараз у руках, ОЧИМА КЛІЄНТА.
    private OZ_PDA_Base Held()
    {
        PlayerBase p = PlayerBase.Cast(GetGame().GetPlayer());
        if (!p || !p.GetHumanInventory())
            return null;

        return OZ_PDA_Base.Cast(p.GetHumanInventory().GetEntityInHands());
    }

    private bool Drifted()
    {
        // Ще нічого не малювали -- питати треба, але не щосекунди після
        // відмови (D13): відмова -- це теж відповідь, і повторювати питання
        // має сенс лише коли щось могло змінитись.
        if (!m_State)
        {
            if (m_FailedAt > 0 && GetGame().GetTime() - m_FailedAt < RETRY_MS)
                return false;
            return true;
        }

        // КПК уже не в руках: меню закриється саме, і смикати сервер по дорозі
        // нема сенсу.
        OZ_PDA_Base pda = Held();
        if (!pda)
            return false;

        if (pda.OZ_IsOn() != m_State.Powered)
            return true;

        OZ_Module_Radio board = OZR_Set.BoardIn(pda);
        if ((board != null) != m_State.HasBoard)
            return true;

        int shown = -1;
        if (board)
            shown = board.OZR_ShownIndex();

        if (shown != m_SyncShown)
        {
            m_SyncShown = shown;
            return true;
        }

        return false;
    }

    private void Ask()
    {
        OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "list", "{}");
    }

    // Книжка -- СВОЯ операція, а не поле стану. Просимо її навмисно: коли
    // зайшли на сторінку, коли самі її змінили і коли місця в пам'яті стало
    // інакше.
    private void AskBook()
    {
        OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "book", "{}");
    }

    private void AskChip()
    {
        OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "chip_read", "{}");
    }

    override bool OnPageClick(Widget w, int x, int y)
    {
        if (w == m_BtnTune)
        {
            Tune(Typed());
            return true;
        }

        if (w == m_BtnUp)
        {
            StepFreq(1);
            return true;
        }

        if (w == m_BtnDown)
        {
            StepFreq(-1);
            return true;
        }

        if (w == m_BtnSave)
        {
            Remember();
            return true;
        }

        if (w == m_BtnForget)
        {
            Forget();
            return true;
        }

        if (w == m_BtnChipA)
        {
            if (m_ChipMode)
                ChipTake();
            else
                OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "chip_write", "{}");
            return true;
        }

        if (w == m_BtnChipB)
        {
            if (m_ChipMode)
                OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "chip_import", "{}");
            else
                EnterChip();
            return true;
        }

        if (w == m_BtnChipC)
        {
            LeaveChip();
            return true;
        }

        return false;
    }

    private void EnterChip()
    {
        m_ChipMode   = true;
        m_ChipRows   = null;
        m_Picked     = -1;
        m_PickedName = "";
        PaintButtons();
        PaintBook();
        AskChip();
    }

    private void LeaveChip()
    {
        m_ChipMode   = false;
        m_Picked     = -1;
        m_PickedName = "";
        PaintButtons();
        PaintBook();
    }

    override void OnResponse(string op, bool ok, string json, string error)
    {
        if (op == "list")
        {
            if (!ok)
            {
                m_FailedAt = GetGame().GetTime();
                Say(error);
                return;
            }

            OZR_RadioState st;
            string err;
            // Copy() -- поки поля ще читаються правильно. Об'єкт із
            // завантажувача створив рушій, тож усе, що він не присвоїв,
            // після першої ж рухомої купи стає сміттям, а тримаємо ми його
            // секундами. Доказ -- над OZR_RadioState.Copy.
            if (JsonFileLoader<OZR_RadioState>.LoadData(json, st, err) && st)
            {
                m_State = st.Copy();
                Paint();
            }
            return;
        }

        if (op == "book")
        {
            if (!ok)
            {
                Say(error);
                return;
            }

            OZR_BookList got;
            string berr;
            if (JsonFileLoader<OZR_BookList>.LoadData(json, got, berr) && got && got.Items)
            {
                m_Rows = got.Copy();
                PaintBook();
            }
            return;
        }

        if (op == "chip_read")
        {
            if (!ok)
            {
                // Чипа немає або він порожній: кажемо чому й лишаємось у
                // режимі чипа з порожнім списком -- кнопка «книжка» поруч.
                m_ChipRows = new OZR_BookList();
                PaintBook();
                Say(error);
                return;
            }

            OZR_BookList chip;
            string cerr;
            if (JsonFileLoader<OZR_BookList>.LoadData(json, chip, cerr) && chip && chip.Items)
            {
                m_ChipRows = chip.Copy();
                PaintBook();
            }
            return;
        }

        if (op == "tune")
        {
            if (ok)
            {
                // Намір виконано: поле знову дзеркало плати. m_FreqShown
                // скидається навмисне -- інакше відповідь не переписала б
                // поле там, де ділення не змінилось (набрали те, на чому вже
                // стояли, або число прилипло до сусіднього каналу), і в полі
                // лишився б сирий набір.
                m_Pending   = -1;
                m_FreqShown = -1;
                Ask();
            }
            else
                Say(error);
            return;
        }

        // Ми самі щойно змінили книжку -- перечитуємо і стан, і її.
        if (op == "save" || op == "forget")
        {
            if (!ok)
            {
                Say(error);
                return;
            }

            Ask();
            AskBook();
            return;
        }

        if (op == "chip_write" || op == "chip_import" || op == "chip_take")
        {
            if (!ok)
            {
                Say(error);
                return;
            }

            OZR_ChipReport rep;
            string rerr;
            string line = "";
            if (JsonFileLoader<OZR_ChipReport>.LoadData(json, rep, rerr) && rep)
            {
                // Копія ДО наступного виділення: між розбором і читанням
                // Taken/Total стоять два пошуки в таблиці рядків, а кожен
                // будує рядок. Доказ -- над OZR_ChipReport.Copy.
                rep = rep.Copy();

                if (op == "chip_write")
                    line = T("STR_OZR_CHIP_WROTE");
                else
                    line = T("STR_OZR_CHIP_TOOK");
                line += ": " + rep.Taken.ToString();

                // «Решта не влізла» -- лише про запис на чип. Забирання з чипа
                // -- усе або нічого (OZR_Page.Merge): те, що не влазить,
                // приходить відмовою, а менше за «на чипі» при успіху беруть
                // тільки тоді, коли частина імен на чипі непридатна.
                if (rep.Taken < rep.Total)
                {
                    line += " / " + rep.Total.ToString();
                    if (op == "chip_write")
                        line += " - " + T("STR_OZR_CHIP_PART");
                }
            }
            SetHintSticky("HintText", line);

            // Обидві сторони могли змінитись: книжка приладу (import/take)
            // або чипа (write). Перечитуємо ту, яку показуємо, і стан -- заради
            // лічильника вільних ячеек.
            Ask();
            AskBook();
            if (m_ChipMode)
                AskChip();
        }
    }

    // Вибір рядка -- виділення й заповнення полів (ТЗ-5 R-E1.1). Настроює
    // TUNE, забуває FORGET, забирає з чипа TAKE -- усі по виділеному.
    //
    // ПЛАТИ ВИБІР НЕ ЧІПАЄ: він кладе частоту рядка в НАМІР, і далі все як із
    // набраною руками.
    override bool OnPageItemSelected(Widget w, int row)
    {
        if (!m_Book || w != m_Book)
            return false;

        OZR_BookList rows = Shown();
        if (!rows || row < 0 || row >= rows.Items.Count())
        {
            m_Picked     = -1;
            m_PickedName = "";
            return true;
        }

        OZR_BookRow r = rows.Items[row];
        m_Picked     = row;
        m_PickedName = r.Name;

        // Видиме виділення -- одразу.
        Repaint();

        // Прямо у віджет: SetText базової сторінки вміє лише TextWidget,
        // а поле вводу -- інший клас.
        if (m_Name)
            m_Name.SetText(r.Name);
        if (r.MHz > 0)
            SetPending(r.Index);

        // Недосяжний рядок вибрати можна -- забути його або переписати ім'я
        // треба вміти, -- а настроїтись на нього не вийде, і причина
        // називається одразу, ще до натискання TUNE.
        if (!r.Reach)
            SetHint("HintText", "#STR_OZR_ERR_OUT_OF_REACH");
        else
            SetHint("HintText", "");

        return true;
    }

    // ------------------------------------------------------------- дії

    // Що набрано в полі, у діленнях ефіру. -1, якщо набрано не число або
    // сервер ще не сказав, з чого рахувати.
    private int Typed()
    {
        if (!m_Freq)
            return -1;

        string text = m_Freq.GetText();
        if (text == "")
            return -1;

        float mhz = text.ToFloat();
        if (mhz <= 0)
            return -1;

        return IndexOf(mhz);
    }

    // МГц -> ділення ефіру, за тими двома числами, що приїхали в стані.
    private int IndexOf(float mhz)
    {
        if (!m_State || m_State.EtherStep <= 0)
            return -1;

        return Math.Round((mhz - m_State.EtherBase) / m_State.EtherStep);
    }

    // Ділення -> МГц, тим самим джерелом.
    private float MHzAt(int index)
    {
        if (!m_State || m_State.EtherStep <= 0)
            return 0;

        return m_State.EtherBase + index * m_State.EtherStep;
    }

    // Вікно ЦІЄЇ ПЛАТИ в діленнях ефіру -- ті самі три числа, якими міряє
    // сервер (OZR_Grid.Window), тільки зі стану сторінки: смуга й крок
    // приїжджають сюди в OZR_RadioState, а OZR_ClientGrid ця сторінка не
    // читає взагалі.
    //
    // Рахуємо в діленнях, а не в МГц: 138.000 із поля й 86.000 + 4160 * 0.0125
    // це те саме число лише в математиці, а у float -- ні. IndexOf округлює, і
    // допуск у пів ділення, який тут стояв, стає непотрібним.
    //
    // СТЕЛІ СІТКИ ТУТ НЕМАЄ: стан її не возить. Профіль, чия верхня межа
    // випереджає живий ефір, дасть намір, який сервер відхилить поіменно
    // (STR_OZR_ERR_OUT_OF_BAND), а не тихо.
    private bool Window(out int lo, out int hi, out int stride)
    {
        lo     = 0;
        hi     = 0;
        stride = 1;

        if (!m_State || m_State.EtherStep <= 0 || m_State.MaxMHz <= 0)
            return false;

        lo     = IndexOf(m_State.MinMHz);
        hi     = IndexOf(m_State.MaxMHz);
        // Той самий підрахунок, що на сервері й у клавіатурі частот -- одним
        // місцем (OZR_Chan).
        stride = OZR_Chan.Stride(m_State.StepMHz, m_State.EtherStep);

        if (lo < 0)
            lo = 0;
        if (hi <= lo)
            return false;

        return true;
    }

    // ЗАПРОПОНУВАТИ частоту: показати її в полі й запам'ятати, що поле тепер
    // гравцеве. Плати це не чіпає -- її рухає лише НАЛАШТУВАТИ.
    private void SetPending(int index)
    {
        m_Pending = index;

        // Прямо у віджет: SetText базової сторінки вміє лише TextWidget, а
        // поле вводу -- інший клас.
        if (m_Freq)
            m_Freq.SetText(OZR_Fmt.MHz(MHzAt(index)));
    }

    private void Tune(int index)
    {
        // Ключ без «#»: підказка додає його сама. З двома ґратками рушій
        // показував сирий "##STR_..." (D98).
        if (index < 0)
        {
            Say("STR_OZR_ERR_OUT_OF_BAND");
            return;
        }

        // Межі ЦІЄЇ ПЛАТИ, а не ефіру: гравець на екрані бачить саме її смугу,
        // і відмова мусить називати ту межу, яка написана над кнопкою.
        int lo;
        int hi;
        int stride;
        if (Window(lo, hi, stride))
        {
            if (index < lo || index > hi)
            {
                Say("STR_OZR_ERR_OUT_OF_BAND");
                return;
            }

            // ПРИЛИПАЄМО ДО ҐРАТКИ, А НЕ ВІДМОВЛЯЄМО -- те саме правило, що в
            // клавіатури частот: набрав 145.13, а плата крокує по 0.05 --
            // мав на увазі 145.15. Без цього сервер відповідав
            // STR_OZR_ERR_OFF_STEP на цілком зрозумілий намір.
            index = OZR_Chan.Snap(index, lo, hi, stride);
        }

        OZR_TuneRef r = new OZR_TuneRef();
        r.Index = index;

        string json;
        string err;
        if (JsonFileLoader<OZR_TuneRef>.MakeData(r, json, err, false))
        {
            OZR_Log.Dbg("page: tune request index " + index.ToString());
            OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "tune", json);
        }
        else
            OZR_Log.Warn("page: tune request not built: " + err);
    }

    // Крок по ґратці ЦІЄЇ плати, а не по діленню сітки: між її каналами
    // стояти нема сенсу.
    //
    // КРОК МІНЯЄ НАМІР, А НЕ ПЛАТУ (рішення власника 2026-09-09). Раніше «+»
    // слав настройку одразу -- і кнопка НАЛАШТУВАТИ поруч не значила нічого.
    //
    // НЕ «Step». Метод із таким ім'ям у скриптовому класі рушій не викликає
    // ВЗАГАЛІ: виклик Step(1) мовчки не виконував жодного рядка тіла, без
    // помилки в лозі (зміряно 2026-09-02, D12 «плюс не зсуває частоту»);
    // перейменування -- і той самий код запрацював.
    private void StepFreq(int dir)
    {
        int lo;
        int hi;
        int stride;
        if (!Window(lo, hi, stride))
            return;

        // Крокуємо від того, що НАБРАНО, якщо набрано щось осмислене: інакше
        // «набрав 140.5, тисну +» відкидало б назад до тієї частоти, на якій
        // стоїмо.
        int from = Typed();
        if (from < 0)
            from = m_State.Index;
        if (from < 0)
            from = lo;

        // Спершу прилипаємо до ґратки плати, потім крокуємо: частота могла
        // стояти між її каналами, якщо профіль щойно правили.
        int target = OZR_Chan.Snap(from, lo, hi, stride) + dir * stride;
        OZR_Log.Dbg("page: step " + dir.ToString() + " from " + from.ToString() + " stride " + stride.ToString() + " -> " + target.ToString());

        // За краєм смуги намір не пропонуємо взагалі -- і кажемо ту саму
        // відмову, яку сторінка казала тут завжди. Обгортання по колу тут
        // немає навмисне: у клавіатури воно є, бо там ручка, а тут число.
        if (target < lo || target > hi)
        {
            Say("STR_OZR_ERR_OUT_OF_BAND");
            return;
        }

        SetPending(target);
    }

    // ---------------------------------------------------------- малювання

    private void Paint()
    {
        if (!m_State)
            return;

        if (!m_State.HasBoard)
        {
            SetText("StatusText", "#STR_OZR_ERR_NO_BOARD");
            SetText("FreqText",   "---");
            SetText("BandText",   "");
            PaintButtons();
            return;
        }

        if (!m_State.Powered)
        {
            SetText("StatusText", "#STR_OZ_ERR_OFF");
            SetText("FreqText",   "---");
            SetText("BandText",   "");
            PaintButtons();
            return;
        }

        if (m_State.Live)
            SetText("StatusText", "#STR_OZR_ON_AIR");
        else
            SetText("StatusText", "#STR_OZR_READY");

        SetText("FreqText", OZR_Fmt.MHz(m_State.FreqMHz) + " MHz");

        // Поле вводу починає з тієї частоти, на якій стоїмо, -- і лишається
        // дзеркалом плати рівно доти, доки гравець нічого не запропонував.
        //
        // ДВІ УМОВИ, І ОБИДВІ ОБОВ'ЯЗКОВІ. m_Pending < 0 -- «поле ще наше»:
        // намір, який людина набрала або вибрала в книжці, ця відповідь не
        // чіпає (вона приходить раз на секунду). m_State.Index != m_FreqShown
        // -- «плата справді переїхала»: інакше безумовний запис затирав би
        // недонабране число.
        if (m_Freq && m_Pending < 0 && m_State.Index != m_FreqShown)
        {
            m_FreqShown = m_State.Index;
            m_Freq.SetText(OZR_Fmt.MHz(m_State.FreqMHz));
        }

        string band = OZR_Fmt.MHz(m_State.MinMHz) + " - " + OZR_Fmt.MHz(m_State.MaxMHz);
        band += " / " + OZR_Fmt.Step(m_State.StepMHz);
        band += "   " + Math.Round(m_State.RangeM).ToString() + " m";
        SetText("BandText", band);

        PaintButtons();

        // СПИСОК ПЕРЕМАЛЬОВУЄМО ЛИШЕ КОЛИ Є ЧОМУ.
        //
        // Paint() приходить на кожну відповідь про стан, тобто раз на секунду
        // при будь-якому русі; PaintBook() чистить листбокс і будує його
        // наново, а це скидає прокрутку й вибір. Саме заради компенсації
        // цього поруч живе повторний пошук виділеного рядка за іменем (D12) --
        // сам факт його існування й був доказом зайвої перебудови.
        //
        // Рядки міняються рівно з двох причин: приїхала книжка (відповіді
        // book / chip_read малюють її самі) або пам'ять приладу стала іншою.
        // Режим чипа сюди не входить взагалі: його список живе своїм життям.
        if (m_ChipMode)
            return;

        if (!m_Rows || MemoryChanged())
            PaintBook();
    }

    // Пам'ять та сама, що й була? Порівнюємо саме те, що сервер шле завжди.
    private bool MemoryChanged()
    {
        return m_State.StoresRecords != m_StoresShown || m_State.FreeCells != m_FreeShown;
    }

    // Які кнопки мають сенс у цьому режимі. Кнопка, якій нема що робити,
    // гірша за її відсутність.
    private void PaintButtons()
    {
        bool chip = m_ChipMode;

        if (m_BtnSave)
            m_BtnSave.Show(!chip);
        if (m_BtnForget)
            m_BtnForget.Show(!chip);

        if (m_BtnChipA)
        {
            m_BtnChipA.Show(true);
            if (chip)
                SetText("BtnChipAText", "#STR_OZR_TAKE");
            else
                SetText("BtnChipAText", "#STR_OZR_TO_CHIP");
        }
        if (m_BtnChipB)
        {
            m_BtnChipB.Show(true);
            if (chip)
                SetText("BtnChipBText", "#STR_OZR_ALL");
            else
                SetText("BtnChipBText", "#STR_OZR_CHIP");
        }
        if (m_BtnChipC)
        {
            m_BtnChipC.Show(chip);
            SetText("BtnChipCText", "#STR_OZR_BOOK");
        }
    }

    // ------------------------------------------------------------ книжка

    // ЗБЕРІГАЄТЬСЯ НАЛАШТОВАНА ЧАСТОТА, А НЕ НАБРАНА (рішення власника
    // 2026-09-09). Ділення бере сервер, прямо з плати (OZR_Page.Save), і
    // прохання його не возить узагалі -- імені досить.
    //
    // Причина проста: книжка -- це імена тому, що рація СПРАВДІ слухає. Запис,
    // зроблений з наміру, який ще не поїхав на плату, обіцяв би частоту, якої
    // ніхто не перевіряв.
    private void Remember()
    {
        if (!m_Name)
            return;

        OZR_FreqEntry r = new OZR_FreqEntry();
        r.Name = m_Name.GetText();

        string json;
        string err;
        if (!JsonFileLoader<OZR_FreqEntry>.MakeData(r, json, err, false))
            return;

        // Намір розійшовся з платою -- кажемо, ЩО САМЕ ляже в книжку. Мовчазна
        // різниця між двома числами на екрані -- найдорожчий спосіб це
        // з'ясувати.
        int want = Typed();
        if (m_State && want >= 0 && want != m_State.Index)
            Say("STR_OZR_SAVED_TUNED");

        OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "save", json);
    }

    private void Forget()
    {
        if (m_ChipMode || !m_Rows || m_Picked < 0 || m_Picked >= m_Rows.Items.Count())
        {
            Say("STR_OZR_ERR_PICK_ONE");
            return;
        }

        OZR_FreqEntry r = new OZR_FreqEntry();
        r.Name = m_Rows.Items[m_Picked].Name;

        string json;
        string err;
        if (JsonFileLoader<OZR_FreqEntry>.MakeData(r, json, err, false))
            OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "forget", json);
    }

    // Одну частоту з чипа -- у прилад (ТЗ-5 R-E5.4, «забрати одну»).
    private void ChipTake()
    {
        if (!m_ChipMode || !m_ChipRows || m_Picked < 0 || m_Picked >= m_ChipRows.Items.Count())
        {
            Say("STR_OZR_ERR_PICK_ONE");
            return;
        }

        OZR_TuneRef r = new OZR_TuneRef();
        r.Index = m_Picked;

        string json;
        string err;
        if (JsonFileLoader<OZR_TuneRef>.MakeData(r, json, err, false))
            OZ_Rpc.Request(OZRP_Const.PAGE_RADIO, "chip_take", json);
    }

    // Той список, який зараз на екрані.
    private OZR_BookList Shown()
    {
        if (m_ChipMode)
            return m_ChipRows;
        return m_Rows;
    }

    private void PaintBook()
    {
        if (!m_Book || !m_State)
            return;

        if (!m_ChipMode)
        {
            // Книжка ще не приїжджала -- малювати нема чого, і чіпати
            // намальоване НЕ МОЖНА.
            if (!m_Rows)
            {
                AskBook();
                return;
            }

            // Місця в пам'яті стало інакше -- отже, книжка змінилась не з цієї
            // сторінки (мітка, нотатка, інший прилад). Перечитуємо.
            if (MemoryChanged())
            {
                m_StoresShown = m_State.StoresRecords;
                m_FreeShown   = m_State.FreeCells;
                AskBook();
            }
        }

        OZR_BookList rows = Shown();

        m_Book.ClearItems();

        if (!rows)
        {
            // Чип ще читається.
            m_Picked = -1;
            SetText("BookFree", "");
            return;
        }

        // Виділення переживає перемальовування: шукаємо той самий рядок за
        // іменем (D12). Номер міг зміститись, ім'я -- ні.
        m_Picked = -1;
        for (int k = 0; k < rows.Items.Count(); k++)
        {
            if (m_PickedName != "" && rows.Items[k].Name == m_PickedName)
                m_Picked = k;
        }
        if (m_Picked < 0)
            m_PickedName = "";

        for (int i = 0; i < rows.Items.Count(); i++)
            m_Book.AddItem(RowText(rows, i), NULL, 0);

        Shade(rows);

        if (m_ChipMode)
        {
            SetText("BookFree", rows.Items.Count().ToString() + " " + T("STR_OZR_ON_CHIP"));
            return;
        }

        // Три різні відповіді про пам'ять (ТЗ-5 R-E5.2), і жодна не про
        // носій: книжка живе в приладі.
        if (!m_State.StoresRecords)
            SetText("BookFree", "#STR_OZR_NO_RECORDS");
        else if (m_State.FreeCells == 0)
            SetText("BookFree", "#STR_OZR_MEMORY_FULL");
        else if (m_State.FreeCells > 0)
            SetText("BookFree", m_State.FreeCells.ToString() + " " + T("STR_OZR_FREE"));
        else
            SetText("BookFree", "");
    }

    // Один рядок списку, в одному місці. Маркер попереду -- це і є видиме
    // виділення: власна підсвітка віджета губиться під кольором, яким ми
    // гасимо недосяжні рядки, а вибір мусить бути видно завжди й однозначно.
    private string RowText(OZR_BookList rows, int i)
    {
        OZR_BookRow e = rows.Items[i];

        string line = " ";
        if (i == m_Picked)
            line = ">";

        line += " " + e.Name + "   " + OZR_Fmt.MHz(e.MHz);

        // Підпис ПЕРЕКЛАДЕНИЙ тут: ключ посеред рядка списку рушій не
        // розгортає, і гравець бачив сирий STR_ (D99).
        if (!e.Reach)
            line += "   " + T("STR_OZR_OUT_OF_REACH");

        return line;
    }

    // Недосяжне ГАСНЕ. Не замість підпису, а разом із ним.
    private void Shade(OZR_BookList rows)
    {
        if (!m_Book || !rows)
            return;

        for (int i = 0; i < rows.Items.Count(); i++)
        {
            if (!rows.Items[i].Reach)
                m_Book.SetItemColor(i, 0, ARGB(255, 115, 115, 125));
        }
    }

    // Перемалювати ЛИШЕ підписи, не чіпаючи ані складу списку, ані прокрутки.
    private void Repaint()
    {
        OZR_BookList rows = Shown();
        if (!m_Book || !rows)
            return;

        for (int i = 0; i < rows.Items.Count(); i++)
            m_Book.SetItem(i, RowText(rows, i), NULL, 0);

        Shade(rows);
    }

    private string T(string key)
    {
        return Widget.TranslateString("#" + key);
    }

    // Те, що сказав сервер, -- у СВІЙ віджет підказки, і липко (D100): раніше
    // відмова писалась у рядок стану, який наступне оновлення затирало
    // раніше, ніж людина встигала прочитати.
    private void Say(string key)
    {
        if (key == "")
            return;
        SetHintSticky("HintText", "#" + key);
    }
}
