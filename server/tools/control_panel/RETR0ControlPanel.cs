// Project RETR0 - control panel for the RETR0 server package ("RETR0 Server.exe").
//
// A window over the existing scripts. It does not replace them: every action runs retr0_server.cmd / client.cmd
// (the package's own wrappers for retr0_server.ps1 / client.ps1), adb, or an HTTP call to the local sync service, so the Python services and scripts stay plain files that can be edited
// and restarted without rebuilding this program. The exe must sit in the server package folder (next to
// retr0_server.ps1); it finds everything relative to its own location.
//
// Build (Windows' own C# compiler, .NET Framework 4.x, C# 5 syntax only):  tools\control_panel\build.cmd
// Independently written for Project RETR0. Listens on nothing; talks only to 127.0.0.1 and adb.
//
// UI (0.4): dark/light theme, left navigation rail, Overview screen, activity feed, "stopped unexpectedly" toast.
// Everything is drawn in code (GDI+ and Segoe MDL2 Assets / Segoe Fluent Icons glyphs); the RETRO logo is a small
// PNG embedded below as base64, so this stays one source file with no image files next to the exe.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("RETR0 Server")]
[assembly: System.Reflection.AssemblyProduct("Project RETR0")]
[assembly: System.Reflection.AssemblyVersion("0.4.0.0")]

namespace Retr0
{
    static class Program
    {
        [DllImport("user32.dll")]
        static extern bool SetProcessDPIAware();

        [STAThread]
        static void Main()
        {
            try { SetProcessDPIAware(); } catch { }   // crisp text at 125/150 % instead of a stretched bitmap
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            float scale = 1f;
            try { using (var g = Graphics.FromHwnd(IntPtr.Zero)) scale = g.DpiX / 96f; } catch { }
            Ui.Init(scale);
            string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            if (!File.Exists(Path.Combine(root, "retr0_server.ps1")))
            {
                MessageBox.Show("RETR0 Server.exe must be in the server package folder, next to retr0_server.ps1.\n\n" +
                                "Folder: " + root, "RETR0 Server", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            Application.Run(new MainForm(root));
        }
    }

    sealed class Product
    {
        public int Id; public string Currency; public long Amount;
        public Product(int id, string currency, long amount) { Id = id; Currency = currency; Amount = amount; }
        public override string ToString()
        {
            return string.Format("{0:N0} {1}   (product {2}, {3})", Amount, Currency, Id,
                Currency == "Gold" ? "claim from Notifications" : "credited at once with a popup");
        }
    }

    // ====================================================================== look and feel
    sealed class Theme
    {
        public bool Dark;
        public Color Bg, Rail, Card, Card2, Line, Ink, Mut, Dim, Acc, Ok, Warn, Bad, Hdr, Input;

        public static readonly Theme DarkTheme = new Theme
        {
            Dark = true, Bg = C(0x0f1216), Rail = C(0x13171c), Card = C(0x181d24), Card2 = C(0x1e242d), Line = C(0x283039),
            Ink = C(0xe7eaf0), Mut = C(0x8d97a6), Dim = C(0x5d6672), Acc = C(0x4c9aff), Ok = C(0x2fbf71),
            Warn = C(0xf0a83a), Bad = C(0xef5350), Hdr = C(0x0b0e12), Input = C(0x0f1216)
        };
        public static readonly Theme LightTheme = new Theme
        {
            Dark = false, Bg = C(0xf3f4f6), Rail = C(0xe9ebef), Card = C(0xffffff), Card2 = C(0xf6f7f9), Line = C(0xdde1e7),
            Ink = C(0x1a1f27), Mut = C(0x5b6573), Dim = C(0x8a94a2), Acc = C(0x0b67d6), Ok = C(0x178a50),
            Warn = C(0xb26a00), Bad = C(0xc62828), Hdr = C(0xffffff), Input = C(0xffffff)
        };
        public static Theme T = DarkTheme;

        // The output console and log view stay dark in both themes.
        public static readonly Color ConBg = C(0x0a0c0f), ConInk = C(0xc8ced8), ConCmd = C(0x7fb6ff), ConOk = C(0x59d08f),
                                     ConErr = C(0xff7b78), ConDim = C(0x6b7684), ConWarn = C(0xf0a83a);

        public static Color C(int rgb) { return Color.FromArgb(255, (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255); }

        public static Color Mix(Color a, Color b, double t)
        {
            return Color.FromArgb(255, (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
        }
    }

    // Segoe MDL2 Assets (Windows 10) / Segoe Fluent Icons (Windows 11) code points.
    static class G
    {
        public const string Overview = "", Server = "", Phone = "", Gift = "", Folder = "",
            Doc = "", Play = "", Stop = "", Restart = "", Info = "", Theme = "",
            Warn = "", Copy = "", Clear = "", Down = "", Up = "", Send = "",
            Edit = "", Devices = "", Check = "", Undo = "", Repair = "", Delete = "",
            OpenFile = "", OpenFolder = "", Console = "";
    }

    static class Ui
    {
        public static float S = 1f;
        public static Font Body, Small, Semi, SemiSmall, H1, Title, Big, Mono, MonoSmall, Tag, Glyph, GlyphBig;
        public const TextFormatFlags Line = TextFormatFlags.NoPrefix | TextFormatFlags.VerticalCenter |
                                            TextFormatFlags.SingleLine | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding;
        public const TextFormatFlags Wrap = TextFormatFlags.NoPrefix | TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl;

        public static void Init(float scale)
        {
            S = scale <= 0 ? 1f : scale;
            Body = new Font("Segoe UI", 9.5f); Small = new Font("Segoe UI", 8.75f);
            Semi = new Font("Segoe UI Semibold", 9.5f); SemiSmall = new Font("Segoe UI Semibold", 8.25f);
            H1 = new Font("Segoe UI Semibold", 15f); Title = new Font("Segoe UI Semibold", 14.5f); Big = new Font("Segoe UI Semibold", 14f);
            Tag = new Font("Segoe UI Semibold", 6.75f);
            Mono = Pick(new[] { "Cascadia Mono", "Consolas" }, 9.5f) ?? new Font("Courier New", 9.5f);
            MonoSmall = Pick(new[] { "Cascadia Mono", "Consolas" }, 9f) ?? new Font("Courier New", 9f);
            Glyph = Pick(new[] { "Segoe Fluent Icons", "Segoe MDL2 Assets" }, 10f);      // null = no icons, text only
            GlyphBig = Pick(new[] { "Segoe Fluent Icons", "Segoe MDL2 Assets" }, 12f);
        }

        static Font Pick(string[] names, float size)
        {
            foreach (var n in names)
            {
                var f = new Font(n, size);
                if (string.Equals(f.Name, n, StringComparison.OrdinalIgnoreCase)) return f;
                f.Dispose();
            }
            return null;
        }

        public static int P(int v) { return (int)Math.Round(v * S); }

        public static GraphicsPath Round(RectangleF r, float rad)
        {
            var p = new GraphicsPath();
            float d = Math.Min(rad * 2, Math.Min(r.Width, r.Height));
            if (d <= 0) { p.AddRectangle(r); return p; }
            p.AddArc(r.X, r.Y, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }

        public static void FillRound(Graphics g, Color c, RectangleF r, float rad)
        {
            using (var b = new SolidBrush(c)) using (var p = Round(r, rad)) g.FillPath(b, p);
        }

        public static void DrawRound(Graphics g, Color c, RectangleF r, float rad, float width)
        {
            using (var pen = new Pen(c, width)) using (var p = Round(r, rad)) g.DrawPath(pen, p);
        }

        public static void Dot(Graphics g, Color c, float cx, float cy, float r)
        {
            using (var b = new SolidBrush(c)) g.FillEllipse(b, cx - r, cy - r, r * 2, r * 2);
        }

        public static void Smooth(Graphics g) { g.SmoothingMode = SmoothingMode.AntiAlias; g.PixelOffsetMode = PixelOffsetMode.HighQuality; }

        public static int TextW(string s, Font f)
        {
            if (string.IsNullOrEmpty(s)) return 0;
            return TextRenderer.MeasureText(s, f, new Size(int.MaxValue, int.MaxValue), TextFormatFlags.NoPrefix | TextFormatFlags.NoPadding).Width;
        }

        public static void Text(Graphics g, string s, Font f, Color c, Rectangle r) { TextRenderer.DrawText(g, s ?? "", f, r, c, Line); }
        public static void TextRight(Graphics g, string s, Font f, Color c, Rectangle r) { TextRenderer.DrawText(g, s ?? "", f, r, c, Line | TextFormatFlags.Right); }

        public static void Icon(Graphics g, string glyph, Color c, Rectangle r, Font f)
        {
            if (f == null || string.IsNullOrEmpty(glyph)) return;
            TextRenderer.DrawText(g, glyph, f, r, c, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter |
                                                    TextFormatFlags.NoPrefix | TextFormatFlags.NoPadding | TextFormatFlags.SingleLine);
        }

        public static Color Surface(Control c) { return c.Parent != null ? c.Parent.BackColor : Theme.T.Bg; }

        public static void UserPainted(Control c)
        {
            typeof(Control).GetMethod("SetStyle", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                .Invoke(c, new object[] { ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                                          ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true });
        }
    }

    static class Native
    {
        [DllImport("dwmapi.dll")]
        static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);
        [DllImport("uxtheme.dll", CharSet = CharSet.Unicode)]
        static extern int SetWindowTheme(IntPtr hwnd, string app, string idList);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        static extern IntPtr SendMessage(IntPtr hwnd, int msg, IntPtr wParam, string lParam);

        // Dark title bar on Windows 10 20H1+ / 11 (attribute 20; 19 on older 10 builds). Does nothing elsewhere.
        public static void DarkTitleBar(Form f, bool dark)
        {
            try
            {
                int v = dark ? 1 : 0;
                if (DwmSetWindowAttribute(f.Handle, 20, ref v, 4) != 0) DwmSetWindowAttribute(f.Handle, 19, ref v, 4);
            }
            catch { }
        }

        // Dark scroll bars on lists and text boxes (Windows 10 1809+). Does nothing elsewhere.
        public static void Scrollbars(Control c, bool dark)
        {
            try { SetWindowTheme(c.Handle, dark ? "DarkMode_Explorer" : "Explorer", null); } catch { }
        }

        public static void Cue(TextBox t, string text)
        {
            try { SendMessage(t.Handle, 0x1501, (IntPtr)1, text); } catch { }   // EM_SETCUEBANNER
        }
    }

    // ====================================================================== controls
    interface IMeasure { int MeasureHeight(int width); }

    enum BtnKind { Normal, Primary, Go, Danger, DangerOutline, Chip }

    sealed class UiButton : Button
    {
        BtnKind kind; bool large, hot, pressed, selected; string glyph;
        public int MinWidth;

        public UiButton(string text, string glyph, BtnKind kind, bool large)
        {
            Ui.UserPainted(this);
            this.glyph = glyph; this.kind = kind; this.large = large;
            Text = text;
            Font = large ? Ui.Semi : Ui.Body;
            Cursor = Cursors.Hand;
            FlatStyle = FlatStyle.Flat; FlatAppearance.BorderSize = 0; UseVisualStyleBackColor = false;
            MinWidth = kind == BtnKind.Chip || string.IsNullOrEmpty(text) ? 0 : Ui.P(large ? 112 : 92);
            Margin = new Padding(0, 0, Ui.P(8), Ui.P(8));
            Size = GetPreferredSize(Size.Empty);
        }

        public BtnKind Kind { get { return kind; } set { if (kind != value) { kind = value; Invalidate(); } } }
        public bool Selected { get { return selected; } set { if (selected != value) { selected = value; Invalidate(); } } }
        public string Glyph { get { return glyph; } set { glyph = value; Invalidate(); } }
        bool HasGlyph { get { return Ui.Glyph != null && !string.IsNullOrEmpty(glyph); } }

        public override Size GetPreferredSize(Size proposed)
        {
            int h = Ui.P(large ? 40 : kind == BtnKind.Chip ? 30 : 32);
            bool hasText = !string.IsNullOrEmpty(Text);
            if (!hasText) return new Size(h, h);
            int w = Ui.P(kind == BtnKind.Chip ? 12 : 14) * 2 + Ui.TextW(Text, Font);
            if (HasGlyph) w += Ui.P(16) + Ui.P(7);
            return new Size(Math.Max(w, MinWidth), h);
        }

        public void Fit() { Size = GetPreferredSize(Size.Empty); }

        protected override void OnMouseEnter(EventArgs e) { hot = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hot = false; pressed = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { if (e.Button == MouseButtons.Left) { pressed = true; Invalidate(); } base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { pressed = false; Invalidate(); base.OnMouseUp(e); }
        protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }

        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; var surface = Ui.Surface(this);
            g.Clear(surface); Ui.Smooth(g);
            Color bg, border, fg; bool filled = false;
            switch (kind)
            {
                case BtnKind.Primary: bg = border = t.Acc; fg = Color.White; filled = true; break;
                case BtnKind.Go: bg = border = t.Ok; fg = Color.White; filled = true; break;
                case BtnKind.Danger: bg = border = t.Bad; fg = Color.White; filled = true; break;
                case BtnKind.DangerOutline: bg = surface; border = Theme.Mix(surface, t.Bad, 0.6); fg = t.Bad; break;
                case BtnKind.Chip:
                    bg = selected ? Theme.Mix(t.Card, t.Acc, 0.16) : t.Card2;
                    border = selected ? Theme.Mix(t.Card, t.Acc, 0.55) : t.Line;
                    fg = selected ? t.Acc : t.Ink; break;
                default: bg = t.Card2; border = t.Line; fg = t.Ink; break;
            }
            if (!Enabled) { fg = t.Dim; if (filled) { bg = t.Card2; border = t.Line; } }
            else if (pressed) bg = filled ? Theme.Mix(bg, Color.Black, 0.15) : Theme.Mix(bg, t.Acc, 0.14);
            else if (hot) { if (filled) bg = Theme.Mix(bg, Color.White, 0.12); else border = kind == BtnKind.DangerOutline ? t.Bad : t.Acc; }

            float rad = Ui.P(5);
            var r = new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f);
            Ui.FillRound(g, bg, r, rad);
            Ui.DrawRound(g, border, r, rad, 1f);
            if (Focused && ShowFocusCues)
                Ui.DrawRound(g, filled ? Color.White : t.Acc, new RectangleF(2.5f, 2.5f, Width - 5.5f, Height - 5.5f), rad - 2, 1f);

            bool hasText = !string.IsNullOrEmpty(Text);
            int gw = HasGlyph ? Ui.P(16) : 0, gap = HasGlyph && hasText ? Ui.P(7) : 0;
            int tw = hasText ? Ui.TextW(Text, Font) : 0;
            int x = Math.Max(Ui.P(8), (Width - gw - gap - tw) / 2);
            if (!hasText) x = (Width - gw) / 2;
            if (HasGlyph) Ui.Icon(g, glyph, fg, new Rectangle(x, 0, gw, Height), Ui.Glyph);
            if (hasText) Ui.Text(g, Text, Font, fg, new Rectangle(x + gw + gap, 0, Math.Max(0, Width - x - gw - gap - Ui.P(6)), Height));
        }
    }

    sealed class Toggle : CheckBox
    {
        public Toggle(string text, bool on, int height)
        {
            Ui.UserPainted(this);
            Text = text; Checked = on; AutoSize = false; Font = Ui.Body; Cursor = Cursors.Hand;
            Size = new Size(Ui.P(34) + Ui.P(9) + Ui.TextW(text, Font) + Ui.P(6), height);
            Margin = new Padding(0, 0, Ui.P(14), Ui.P(8));
        }

        protected override void OnCheckedChanged(EventArgs e) { base.OnCheckedChanged(e); Invalidate(); }

        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics;
            g.Clear(Ui.Surface(this)); Ui.Smooth(g);
            int w = Ui.P(34), h = Ui.P(18), y = (Height - h) / 2;
            var track = new RectangleF(1, y, w, h);
            Ui.FillRound(g, Checked ? t.Acc : t.Dim, track, h / 2f);
            if (Focused && ShowFocusCues) Ui.DrawRound(g, t.Ink, RectangleF.Inflate(track, 1.5f, 1.5f), h / 2f + 1.5f, 1f);
            float k = h - Ui.P(6), kx = Checked ? 1 + w - Ui.P(3) - k : 1 + Ui.P(3);
            using (var b = new SolidBrush(Color.White)) g.FillEllipse(b, kx, y + Ui.P(3), k, k);
            Ui.Text(g, Text, Font, Enabled ? t.Ink : t.Dim, new Rectangle(w + Ui.P(9), 0, Width - w - Ui.P(9), Height));
        }
    }

    // Grey explanatory text under a row of buttons.
    sealed class Hint : Label
    {
        public Hint(string text) { Text = text; AutoSize = false; Font = Ui.Body; UseMnemonic = false; ForeColor = Theme.T.Mut; }
    }

    // A rounded panel that stacks its rows top to bottom and sizes them itself (one row can fill the rest).
    class Card : Panel, IMeasure
    {
        public string Title, Note; public bool Danger; public Control FillRow; public int FillMin;
        readonly List<Control> rows = new List<Control>();

        public Card(string title, string note)
        {
            Title = title; Note = note; DoubleBuffered = true; ResizeRedraw = true;
            int p = Ui.P(16);
            Padding = new Padding(p, title != null ? Ui.P(44) : Ui.P(14), p, Ui.P(12));
            FillMin = Ui.P(130);
        }

        public T Add<T>(T c) where T : Control { rows.Add(c); Controls.Add(c); return c; }
        public void SetNote(string note) { if (note != Note) { Note = note; Invalidate(); } }
        static int Gap { get { return Ui.P(8); } }

        static int RowHeight(Control c, int w)
        {
            var m = c as IMeasure; if (m != null) return m.MeasureHeight(w);
            var f = c as FlowLayoutPanel; if (f != null) return f.GetPreferredSize(new Size(Math.Max(1, w), 0)).Height;
            var l = c as Label;
            if (l != null) return TextRenderer.MeasureText(l.Text, l.Font, new Size(Math.Max(1, w), int.MaxValue), Ui.Wrap).Height + Ui.P(2);
            return c.Height;
        }

        public int MeasureHeight(int width)
        {
            int w = width - Padding.Horizontal, h = Padding.Vertical;
            for (int i = 0; i < rows.Count; i++)
                h += (i > 0 ? Gap : 0) + (rows[i] == FillRow ? FillMin : RowHeight(rows[i], w));   // never the fill row's current height
            return h;
        }

        protected override void OnLayout(LayoutEventArgs e)
        {
            int w = Math.Max(0, ClientSize.Width - Padding.Horizontal);
            int after = 0; bool seen = false;
            foreach (var c in rows) { if (seen) after += Gap + RowHeight(c, w); if (c == FillRow) seen = true; }
            int y = Padding.Top;
            foreach (var c in rows)
            {
                int h = c == FillRow ? Math.Max(Ui.P(60), ClientSize.Height - Padding.Bottom - y - after) : RowHeight(c, w);
                c.SetBounds(Padding.Left, y, w, h);
                y += h + Gap;
            }
        }

        protected override void OnPaintBackground(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics;
            g.Clear(Ui.Surface(this)); Ui.Smooth(g);
            var r = new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f);
            Ui.FillRound(g, BackColor, r, Ui.P(8));
            Ui.DrawRound(g, Danger ? Theme.Mix(t.Card, t.Bad, 0.55) : t.Line, r, Ui.P(8), 1f);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            if (Title == null) return;
            var t = Theme.T; var g = e.Graphics;
            int x = Padding.Left, y = Ui.P(12), h = Ui.P(22), right = Width - Padding.Right;
            if (Danger && Ui.Glyph != null) { Ui.Icon(g, G.Warn, t.Bad, new Rectangle(x, y, Ui.P(16), h), Ui.Glyph); x += Ui.P(24); }
            int tw = Ui.TextW(Title, Ui.Semi) + Ui.P(2);
            Ui.Text(g, Title, Ui.Semi, Danger ? t.Bad : t.Ink, new Rectangle(x, y, Math.Min(tw, right - x), h));
            if (!string.IsNullOrEmpty(Note))
                Ui.TextRight(g, Note, Ui.Small, t.Mut, new Rectangle(x + tw + Ui.P(12), y, Math.Max(0, right - x - tw - Ui.P(12)), h));
        }
    }

    // A scrollable screen laid out on a 12-column grid. Cells in a row share one height; a "fill" row takes the
    // leftover height. Below ~620 px of width every cell gets its own line.
    sealed class Page : Panel
    {
        sealed class Cell { public Control C; public int Span; }
        sealed class Row { public List<Cell> Cells = new List<Cell>(); public bool Fill; }
        sealed class Placed { public Control C; public int X, W; }
        sealed class Line { public List<Placed> Items = new List<Placed>(); public bool Fill; public int H; }

        readonly List<Row> rows = new List<Row>();
        readonly HashSet<Control> hidden = new HashSet<Control>();
        bool busy;

        public Page()
        {
            AutoScroll = true; DoubleBuffered = true; Dock = DockStyle.Fill; Visible = false;
            Padding = new Padding(Ui.P(18), Ui.P(14), Ui.P(18), Ui.P(16));
        }

        public void AddRow(bool fill, params object[] spanThenControl)
        {
            var r = new Row { Fill = fill };
            for (int i = 0; i + 1 < spanThenControl.Length; i += 2)
            {
                var c = (Control)spanThenControl[i + 1];
                r.Cells.Add(new Cell { Span = (int)spanThenControl[i], C = c });
                Controls.Add(c);
            }
            rows.Add(r);
        }

        public void SetHidden(Control c, bool hide)
        {
            bool changed = hide ? hidden.Add(c) : hidden.Remove(c);
            c.Visible = !hide;
            if (changed) PerformLayout();
        }

        protected override void OnSizeChanged(EventArgs e) { base.OnSizeChanged(e); PerformLayout(); }

        static int Measure(Control c, int w) { var m = c as IMeasure; return m != null ? m.MeasureHeight(w) : c.Height; }

        protected override void OnLayout(LayoutEventArgs e)
        {
            if (busy) return;
            busy = true;
            try
            {
                for (int pass = 0; pass < 3; pass++)
                {
                    int before = ClientSize.Width;
                    Arrange();
                    if (ClientSize.Width == before) break;
                }
            }
            finally { busy = false; }
        }

        void Arrange()
        {
            int gap = Ui.P(12), W = Math.Max(Ui.P(200), ClientSize.Width - Padding.Horizontal);
            bool narrow = W < Ui.P(620);
            var lines = new List<Line>();
            foreach (var r in rows)
            {
                var vis = r.Cells.Where(c => !hidden.Contains(c.C)).ToList();
                if (vis.Count == 0) continue;
                if (narrow)
                {
                    foreach (var c in vis)
                    {
                        var ln = new Line { Fill = r.Fill && c == vis[vis.Count - 1] };
                        ln.Items.Add(new Placed { C = c.C, X = 0, W = W });
                        lines.Add(ln);
                    }
                }
                else
                {
                    var ln = new Line { Fill = r.Fill };
                    int total = vis.Sum(c => c.Span), avail = W - gap * (vis.Count - 1), x = 0;
                    for (int i = 0; i < vis.Count; i++)
                    {
                        int w = i == vis.Count - 1 ? W - x : (int)(avail * (double)vis[i].Span / total);
                        ln.Items.Add(new Placed { C = vis[i].C, X = x, W = w });
                        x += w + gap;
                    }
                    lines.Add(ln);
                }
            }
            int fixedH = Padding.Vertical + gap * Math.Max(0, lines.Count - 1), fills = 0;
            foreach (var ln in lines)
            {
                ln.H = ln.Items.Max(p => Measure(p.C, p.W));
                if (ln.Fill) fills++; else fixedH += ln.H;
            }
            if (fills > 0)
            {
                int share = (ClientSize.Height - fixedH) / fills;
                foreach (var ln in lines) if (ln.Fill) ln.H = Math.Max(ln.H, share);
            }
            int y = Padding.Top; var off = AutoScrollPosition;
            foreach (var ln in lines)
            {
                foreach (var p in ln.Items) p.C.SetBounds(Padding.Left + p.X + off.X, y + off.Y, p.W, ln.H);
                y += ln.H + gap;
            }
            int height = y - gap + Padding.Bottom;
            var want = new Size(0, height > ClientSize.Height ? height : 0);
            if (AutoScrollMinSize != want) AutoScrollMinSize = want;
        }
    }

    sealed class PageTitle : Control, IMeasure
    {
        readonly string sub;
        public PageTitle(string title, string sub) { Ui.UserPainted(this); Text = title; this.sub = sub; TabStop = false; }
        public int MeasureHeight(int width) { return Ui.P(32); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; g.Clear(Ui.Surface(this));
            int tw = Ui.TextW(Text, Ui.H1) + Ui.P(4);
            Ui.Text(g, Text, Ui.H1, t.Ink, new Rectangle(0, 0, tw, Height));
            Ui.Text(g, sub, Ui.Small, t.Mut, new Rectangle(tw + Ui.P(10), Ui.P(3), Math.Max(0, Width - tw - Ui.P(10)), Height));
        }
    }

    // Big status line: coloured dot, "Running", and a quieter detail.
    sealed class StateLine : Control, IMeasure
    {
        Color dot = Color.Gray; string big = "Checking…", small = "";
        public StateLine() { Ui.UserPainted(this); TabStop = false; }
        public void Set(Color d, string b, string s)
        {
            if (d == dot && b == big && s == small) return;
            dot = d; big = b; small = s; Invalidate();
        }
        public int MeasureHeight(int width) { return Ui.P(38); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; g.Clear(Ui.Surface(this)); Ui.Smooth(g);
            Ui.Dot(g, dot, Ui.P(7), Height / 2f, Ui.P(6));
            int bw = Ui.TextW(big, Ui.Big) + Ui.P(4);
            Ui.Text(g, big, Ui.Big, t.Ink, new Rectangle(Ui.P(22), 0, bw, Height));
            Ui.Text(g, small, Ui.Body, t.Mut, new Rectangle(Ui.P(22) + bw + Ui.P(8), Ui.P(3), Math.Max(0, Width - bw - Ui.P(30)), Height));
        }
    }

    sealed class ServiceTiles : Control, IMeasure
    {
        public readonly string[] Names = { "DNS", "CDN", "Sync", "Emulator" };
        public readonly bool[] On = new bool[4];
        public readonly string[] Detail = { "", "", "", "" };
        public bool Known;
        public ServiceTiles() { Ui.UserPainted(this); TabStop = false; }
        int Cols(int w) { return w < Ui.P(460) ? 2 : 4; }
        public int MeasureHeight(int width) { int rows = 4 / Cols(width); return rows * Ui.P(54) + (rows - 1) * Ui.P(8); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; g.Clear(Ui.Surface(this)); Ui.Smooth(g);
            int cols = Cols(Width), gap = Ui.P(8), w = (Width - gap * (cols - 1)) / cols, h = Ui.P(54);
            for (int i = 0; i < 4; i++)
            {
                int x = (i % cols) * (w + gap), y = (i / cols) * (h + gap);
                var r = new RectangleF(x + 0.5f, y + 0.5f, w - 1, h - 1);
                Ui.FillRound(g, t.Card2, r, Ui.P(7)); Ui.DrawRound(g, t.Line, r, Ui.P(7), 1f);
                Ui.Dot(g, !Known ? t.Dim : On[i] ? t.Ok : t.Bad, x + Ui.P(16), y + Ui.P(18), Ui.P(4));
                Ui.Text(g, Names[i], Ui.Semi, t.Ink, new Rectangle(x + Ui.P(26), y + Ui.P(7), w - Ui.P(32), Ui.P(22)));
                Ui.Text(g, Detail[i], Ui.Small, t.Mut, new Rectangle(x + Ui.P(12), y + Ui.P(28), w - Ui.P(18), Ui.P(20)));
            }
        }
    }

    sealed class SubHeader : Control, IMeasure
    {
        readonly string link; Rectangle linkRect;
        public event EventHandler LinkClicked;
        public SubHeader(string text, string link) { Ui.UserPainted(this); Text = text; this.link = link; TabStop = false; }
        public int MeasureHeight(int width) { return Ui.P(26); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; g.Clear(Ui.Surface(this));
            Ui.Text(g, Text, Ui.Semi, t.Ink, new Rectangle(0, 0, Width / 2, Height));
            int lw = Ui.TextW(link, Ui.Body) + Ui.P(2);
            linkRect = new Rectangle(Width - lw, 0, lw, Height);
            Ui.Text(g, link, Ui.Body, t.Acc, linkRect);
        }
        protected override void OnMouseMove(MouseEventArgs e) { Cursor = linkRect.Contains(e.Location) ? Cursors.Hand : Cursors.Default; base.OnMouseMove(e); }
        protected override void OnMouseClick(MouseEventArgs e)
        {
            if (linkRect.Contains(e.Location) && LinkClicked != null) LinkClicked(this, EventArgs.Empty);
            base.OnMouseClick(e);
        }
    }

    sealed class Banner : Control, IMeasure
    {
        public Banner(string text) { Ui.UserPainted(this); Text = text; TabStop = false; }
        public int MeasureHeight(int width) { return Ui.P(38); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; g.Clear(Ui.Surface(this)); Ui.Smooth(g);
            Ui.FillRound(g, Theme.Mix(t.Bg, t.Warn, t.Dark ? 0.16 : 0.12), new RectangleF(0, 0, Width - 1, Height - 1), Ui.P(6));
            Ui.Icon(g, G.Warn, t.Warn, new Rectangle(Ui.P(10), 0, Ui.P(18), Height), Ui.Glyph);
            Ui.Text(g, Text, Ui.Body, t.Warn, new Rectangle(Ui.P(36), 0, Width - Ui.P(44), Height));
        }
    }

    sealed class DangerRow : Panel, IMeasure
    {
        readonly string title, desc; readonly UiButton button;
        public DangerRow(string title, string desc, UiButton button)
        {
            this.title = title; this.desc = desc; this.button = button;
            DoubleBuffered = true; ResizeRedraw = true;
            button.Margin = Padding.Empty;
            Controls.Add(button);
        }
        int TextWidth(int w) { return Math.Max(Ui.P(80), w - button.Width - Ui.P(20)); }
        public int MeasureHeight(int w)
        {
            int h = Ui.P(12) + Ui.P(22) + TextRenderer.MeasureText(desc, Ui.Body, new Size(TextWidth(w), int.MaxValue), Ui.Wrap).Height + Ui.P(10);
            return Math.Max(h, button.Height + Ui.P(24));
        }
        protected override void OnLayout(LayoutEventArgs e) { if (button == null) return; button.Location = new Point(Width - button.Width, (Height - button.Height) / 2 + Ui.P(2)); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics;
            using (var p = new Pen(Theme.Mix(BackColor, t.Bad, 0.3))) g.DrawLine(p, 0, 0, Width, 0);
            int tw = TextWidth(Width);
            Ui.Text(g, title, Ui.Semi, t.Ink, new Rectangle(0, Ui.P(12), tw, Ui.P(22)));
            TextRenderer.DrawText(g, desc, Ui.Body, new Rectangle(0, Ui.P(34), tw, Height - Ui.P(34)), t.Mut, Ui.Wrap);
        }
    }

    // Label above an input, for the custom gift row.
    sealed class FieldBox : Panel
    {
        public FieldBox(string label, Control input, int width)
        {
            var l = new Hint(label) { Location = Point.Empty, Size = new Size(width, Ui.P(19)), Font = Ui.Small };
            input.Location = new Point(0, Ui.P(20)); input.Width = width; input.Margin = Padding.Empty;
            Controls.Add(l); Controls.Add(input);
            Size = new Size(width, Ui.P(20) + input.Height);
            Margin = new Padding(0, 0, Ui.P(10), Ui.P(8));
        }
    }

    sealed class NavButton : Button
    {
        readonly string glyph; string badge; bool selected, hot;
        public readonly string Key;
        public NavButton(string key, string text, string glyph)
        {
            Ui.UserPainted(this);
            Key = key; Text = text; this.glyph = glyph;
            Font = Ui.Body; Cursor = Cursors.Hand; FlatStyle = FlatStyle.Flat; FlatAppearance.BorderSize = 0;
        }
        public bool Selected { get { return selected; } set { if (selected != value) { selected = value; Invalidate(); } } }
        public string Badge { get { return badge; } set { if (badge != value) { badge = value; Invalidate(); } } }
        protected override void OnMouseEnter(EventArgs e) { hot = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hot = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; g.Clear(Ui.Surface(this)); Ui.Smooth(g);
            if (selected || hot) Ui.FillRound(g, t.Card2, new RectangleF(0, 0, Width - 1, Height - 1), Ui.P(6));
            if (selected) Ui.FillRound(g, t.Acc, new RectangleF(0, Ui.P(10), Ui.P(3), Height - Ui.P(20)), 1.5f);
            if (Focused && ShowFocusCues) Ui.DrawRound(g, t.Acc, new RectangleF(1, 1, Width - 3, Height - 3), Ui.P(6), 1f);
            Color fg = selected || hot ? t.Ink : t.Mut;
            Ui.Icon(g, glyph, fg, new Rectangle(Ui.P(12), 0, Ui.P(18), Height), Ui.Glyph);
            int x = Ui.Glyph != null ? Ui.P(42) : Ui.P(14), right = Width - Ui.P(8);
            if (!string.IsNullOrEmpty(badge))
            {
                int bw = Ui.TextW(badge, Ui.SemiSmall) + Ui.P(14), bh = Ui.P(18);
                var br = new RectangleF(right - bw, (Height - bh) / 2f, bw, bh);
                Ui.FillRound(g, Theme.Mix(t.Rail, t.Warn, t.Dark ? 0.2 : 0.14), br, bh / 2f);
                TextRenderer.DrawText(g, badge, Ui.SemiSmall, Rectangle.Round(br), t.Warn,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix | TextFormatFlags.SingleLine);
                right -= bw + Ui.P(6);
            }
            Ui.Text(g, Text, selected ? Ui.Semi : Ui.Body, fg, new Rectangle(x, 0, Math.Max(0, right - x), Height));
        }
    }

    sealed class Rail : Panel
    {
        public readonly List<NavButton> Items = new List<NavButton>();
        readonly string folder;
        public Rail(string folder)
        {
            this.folder = folder; Dock = DockStyle.Left; Width = Ui.P(200); DoubleBuffered = true; ResizeRedraw = true;
        }
        public NavButton Add(NavButton b) { Items.Add(b); Controls.Add(b); return b; }
        protected override void OnLayout(LayoutEventArgs e)
        {
            int y = Ui.P(10);
            foreach (var b in Items) { b.SetBounds(Ui.P(8), y, Width - Ui.P(17), Ui.P(38)); y += Ui.P(41); }
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics;
            using (var p = new Pen(t.Line)) { g.DrawLine(p, Width - 1, 0, Width - 1, Height); g.DrawLine(p, Ui.P(8), Height - Ui.P(52), Width - Ui.P(9), Height - Ui.P(52)); }
            Ui.Text(g, "Folder", Ui.Small, t.Dim, new Rectangle(Ui.P(16), Height - Ui.P(46), Width - Ui.P(24), Ui.P(18)));
            TextRenderer.DrawText(g, folder, Ui.MonoSmall, new Rectangle(Ui.P(16), Height - Ui.P(27), Width - Ui.P(24), Ui.P(20)), t.Mut,
                TextFormatFlags.NoPrefix | TextFormatFlags.SingleLine | TextFormatFlags.PathEllipsis | TextFormatFlags.NoPadding);
        }
    }

    sealed class HeaderBar : Panel
    {
        readonly Image logo;
        public readonly UiButton ThemeButton;
        public readonly bool[] Lights = new bool[4];
        public bool Known, EmuKnown;
        public string PillText = "Checking…", PillDetail = "";
        public Color PillColor = Color.Gray;
        static readonly string[] names = { "DNS", "CDN", "Sync", "Emulator" }, ports = { "", ":8780", ":8781", "" };

        public HeaderBar(Image logo)
        {
            this.logo = logo; Dock = DockStyle.Top; Height = Ui.P(76); DoubleBuffered = true; ResizeRedraw = true;
            ThemeButton = new UiButton("", G.Theme, BtnKind.Normal, false);
            if (Ui.Glyph == null) { ThemeButton.Text = "Theme"; ThemeButton.Fit(); }
            Controls.Add(ThemeButton);
        }

        protected override void OnLayout(LayoutEventArgs e)
        {
            if (ThemeButton == null) return;
            ThemeButton.Location = new Point(Width - Ui.P(16) - ThemeButton.Width, (Height - ThemeButton.Height) / 2);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; Ui.Smooth(g);
            using (var p = new Pen(t.Line)) g.DrawLine(p, 0, Height - 1, Width, Height - 1);
            int x = Ui.P(14);
            if (logo != null)
            {
                int h = Ui.P(54), w = logo.Width * h / logo.Height;
                var r = new Rectangle(x, (Height - h) / 2, w, h);
                if (!t.Dark) Ui.FillRound(g, Color.FromArgb(11, 14, 18), RectangleF.Inflate(r, Ui.P(4), 0), Ui.P(7));
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(logo, r);
                x += w + Ui.P(10);
            }
            else
            {
                int lw = Ui.TextW("RETR0", Ui.Title);
                Ui.Text(g, "RETR0", Ui.Title, t.Ink, new Rectangle(x, 0, lw + 4, Height));
                x += lw + Ui.P(8);
            }

            // right to left: theme button, service chips, then the server pill after the title
            int right = ThemeButton.Left - Ui.P(12);
            var cw = new int[4]; int chipsW = Ui.P(6) * 3;
            for (int i = 0; i < 4; i++)
            {
                cw[i] = Ui.P(10) + Ui.P(8) + Ui.P(7) + Ui.TextW(names[i], Ui.Body) + (ports[i].Length > 0 ? Ui.P(3) + Ui.TextW(ports[i], Ui.Small) : 0) + Ui.P(11);
                chipsW += cw[i];
            }
            const string title = "SERVER", sub = "Project RETR0 · local preservation server · 127.0.0.1";
            int titleW = Ui.TextW(title, Ui.Title), subW = Ui.TextW(sub, Ui.Small);
            int pillCore = Ui.P(38) + Ui.TextW(PillText, Ui.Semi) + Ui.P(14);
            int detailW = PillDetail.Length > 0 ? Ui.P(6) + Ui.TextW(PillDetail, Ui.Small) : 0;
            int chipsX = right - chipsW;
            bool showSub = x + Math.Max(titleW, subW) + Ui.P(20) + pillCore + detailW + Ui.P(16) <= chipsX;
            int textW = showSub ? Math.Max(titleW, subW) : titleW;
            bool showDetail = x + textW + Ui.P(20) + pillCore + detailW + Ui.P(16) <= chipsX;
            bool showPill = x + textW + Ui.P(20) + pillCore + Ui.P(16) <= chipsX;

            if (showSub)
            {
                Ui.Text(g, title, Ui.Title, t.Ink, new Rectangle(x, Height / 2 - Ui.P(24), titleW + 4, Ui.P(28)));
                Ui.Text(g, sub, Ui.Small, t.Mut, new Rectangle(x, Height / 2 + Ui.P(3), subW + 4, Ui.P(20)));
            }
            else Ui.Text(g, title, Ui.Title, t.Ink, new Rectangle(x, 0, titleW + 4, Height));
            x += textW + Ui.P(20);

            if (showPill)
            {
                int pw = pillCore + (showDetail ? detailW : 0), ph = Ui.P(34);
                var pr = new RectangleF(x, (Height - ph) / 2f, pw, ph);
                Ui.FillRound(g, Theme.Mix(t.Hdr, PillColor, t.Dark ? 0.16 : 0.11), pr, ph / 2f);
                float cx = x + Ui.P(18), cy = Height / 2f;
                Ui.Dot(g, Theme.Mix(t.Hdr, PillColor, 0.35), cx, cy, Ui.P(9));
                Ui.Dot(g, PillColor, cx, cy, Ui.P(6));
                int tx = x + Ui.P(32), ptw = Ui.TextW(PillText, Ui.Semi) + Ui.P(2);
                Ui.Text(g, PillText, Ui.Semi, PillColor, new Rectangle(tx, 0, ptw, Height));
                if (showDetail) Ui.Text(g, PillDetail, Ui.Small, t.Mut, new Rectangle(tx + ptw + Ui.P(6), Ui.P(1), detailW, Height));
            }

            int chx = chipsX, chh = Ui.P(30), chy = (Height - chh) / 2;
            for (int i = 0; i < 4; i++)
            {
                var r = new RectangleF(chx + 0.5f, chy + 0.5f, cw[i] - 1, chh - 1);
                Ui.FillRound(g, t.Card, r, Ui.P(6)); Ui.DrawRound(g, t.Line, r, Ui.P(6), 1f);
                bool known = i == 3 ? EmuKnown : Known;
                Ui.Dot(g, !known ? t.Dim : Lights[i] ? t.Ok : t.Bad, chx + Ui.P(14), Height / 2f, Ui.P(4));
                int nx = chx + Ui.P(25), nw = Ui.TextW(names[i], Ui.Body) + 2;
                Ui.Text(g, names[i], Ui.Body, t.Ink, new Rectangle(nx, 0, nw, Height));
                if (ports[i].Length > 0) Ui.Text(g, ports[i], Ui.Small, t.Mut, new Rectangle(nx + nw + Ui.P(1), Ui.P(1), cw[i], Height));
                chx += cw[i] + Ui.P(6);
            }
        }
    }

    sealed class DockBar : Panel
    {
        public string Status = ""; public bool Busy; public float Angle;
        public readonly FlowLayoutPanel Buttons;
        public DockBar()
        {
            Dock = DockStyle.Top; Height = Ui.P(40); DoubleBuffered = true; ResizeRedraw = true;
            Buttons = new FlowLayoutPanel { Dock = DockStyle.Right, FlowDirection = FlowDirection.RightToLeft, WrapContents = false,
                                            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(0, Ui.P(5), Ui.P(6), 0) };
            Controls.Add(Buttons);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; Ui.Smooth(g);
            using (var p = new Pen(t.Line)) g.DrawLine(p, 0, 0, Width, 0);
            int x = Ui.P(12);
            if (Ui.Glyph != null) { Ui.Icon(g, G.Console, t.Mut, new Rectangle(x, 0, Ui.P(16), Height), Ui.Glyph); x += Ui.P(24); }
            int ow = Ui.TextW("Output", Ui.Semi) + Ui.P(2);
            Ui.Text(g, "Output", Ui.Semi, t.Ink, new Rectangle(x, 0, ow, Height));
            x += ow + Ui.P(14);
            int right = Buttons.Left - Ui.P(8);
            if (Busy)
            {
                int s = Ui.P(12);
                using (var pen = new Pen(t.Acc, Math.Max(2f, Ui.S * 2f))) g.DrawArc(pen, x, (Height - s) / 2f, s, s, Angle, 270);
                x += s + Ui.P(8);
            }
            Ui.Text(g, Status, Ui.Body, Busy ? t.Acc : t.Mut, new Rectangle(x, 0, Math.Max(0, right - x), Height));
        }
    }

    sealed class Toast : Panel
    {
        public string Title = "", Body = "";
        public readonly FlowLayoutPanel Actions;
        public Toast()
        {
            Size = new Size(Ui.P(380), Ui.P(112)); DoubleBuffered = true; ResizeRedraw = true; Visible = false;
            Actions = new FlowLayoutPanel { Location = new Point(Ui.P(44), Ui.P(68)), Size = new Size(Ui.P(330), Ui.P(36)), WrapContents = false };
            Controls.Add(Actions);
        }
        protected override void OnSizeChanged(EventArgs e)
        {
            base.OnSizeChanged(e);
            using (var p = Ui.Round(new RectangleF(0, 0, Width, Height), Ui.P(8))) Region = new Region(p);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; Ui.Smooth(g);
            Ui.DrawRound(g, t.Line, new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), Ui.P(8), 1f);
            using (var b = new SolidBrush(t.Warn)) g.FillRectangle(b, 0, 0, Ui.P(4), Height);
            Ui.Icon(g, G.Warn, t.Warn, new Rectangle(Ui.P(14), Ui.P(12), Ui.P(20), Ui.P(22)), Ui.GlyphBig);
            Ui.Text(g, Title, Ui.Semi, t.Ink, new Rectangle(Ui.P(44), Ui.P(12), Width - Ui.P(54), Ui.P(22)));
            TextRenderer.DrawText(g, Body, Ui.Small, new Rectangle(Ui.P(44), Ui.P(34), Width - Ui.P(54), Ui.P(34)), t.Mut, Ui.Wrap);
        }
    }

    enum FeedKind { Info, Good, Bad, Quiet, Accent }
    sealed class FeedItem { public DateTime When; public string Text; public FeedKind Kind; }

    sealed class FeedList : ListBox
    {
        public FeedList()
        {
            DrawMode = DrawMode.OwnerDrawFixed; ItemHeight = Math.Min(255, Ui.P(26)); BorderStyle = BorderStyle.None;
            IntegralHeight = false; SelectionMode = SelectionMode.None; Font = Ui.Body;
        }
        public void Push(FeedItem f) { Items.Insert(0, f); if (Items.Count > 300) Items.RemoveAt(Items.Count - 1); }
        protected override void OnDrawItem(DrawItemEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; var r = e.Bounds;
            using (var b = new SolidBrush(t.Card)) g.FillRectangle(b, r);
            if (e.Index < 0 || e.Index >= Items.Count) return;
            var f = (FeedItem)Items[e.Index];
            using (var p = new Pen(t.Line)) g.DrawLine(p, r.Left, r.Bottom - 1, r.Right, r.Bottom - 1);
            Ui.Text(g, f.When.ToString("HH:mm"), Ui.MonoSmall, t.Dim, new Rectangle(r.X, r.Y, Ui.P(46), r.Height));
            Color c = f.Kind == FeedKind.Good ? t.Ok : f.Kind == FeedKind.Bad ? t.Bad : f.Kind == FeedKind.Accent ? t.Acc : f.Kind == FeedKind.Quiet ? t.Dim : t.Mut;
            Ui.Smooth(g); Ui.Dot(g, c, r.X + Ui.P(56), r.Y + r.Height / 2f, Ui.P(4)); g.SmoothingMode = SmoothingMode.None;
            Ui.Text(g, f.Text, Ui.Body, t.Ink, new Rectangle(r.X + Ui.P(68), r.Y, r.Width - Ui.P(70), r.Height));
        }
    }

    // Details ListView with themed header, row lines, status badges and file-type tags.
    sealed class ThemedList : ListView
    {
        public int BadgeColumn = -1, MutedColumn = -1, LastMin = Ui.P(120); public bool TypeTags;
        readonly ImageList rowHeight = new ImageList();
        bool fitting;

        public ThemedList()
        {
            OwnerDraw = true; View = View.Details; FullRowSelect = true; DoubleBuffered = true; BorderStyle = BorderStyle.None;
            HeaderStyle = ColumnHeaderStyle.Nonclickable; MultiSelect = false; HideSelection = false; ShowItemToolTips = true;
            rowHeight.ImageSize = new Size(1, Math.Min(256, Ui.P(26))); SmallImageList = rowHeight;
            Font = Ui.Body;
        }

        // The last column always reaches the right edge, so no unpainted header strip is left over.
        public void FitLastColumn()
        {
            if (Columns.Count == 0 || fitting) return;
            fitting = true;
            try
            {
                int used = 0;
                for (int i = 0; i < Columns.Count - 1; i++) used += Columns[i].Width;
                int w = Math.Max(LastMin, ClientSize.Width - used);
                if (Columns[Columns.Count - 1].Width != w) Columns[Columns.Count - 1].Width = w;
            }
            finally { fitting = false; }
        }

        protected override void OnSizeChanged(EventArgs e) { base.OnSizeChanged(e); FitLastColumn(); }

        static TextFormatFlags Align(HorizontalAlignment a) { return Ui.Line | (a == HorizontalAlignment.Right ? TextFormatFlags.Right : 0); }

        protected override void OnDrawColumnHeader(DrawListViewColumnHeaderEventArgs e)
        {
            var t = Theme.T;
            using (var b = new SolidBrush(t.Card)) e.Graphics.FillRectangle(b, e.Bounds);
            using (var p = new Pen(t.Line)) e.Graphics.DrawLine(p, e.Bounds.Left, e.Bounds.Bottom - 1, e.Bounds.Right, e.Bounds.Bottom - 1);
            TextRenderer.DrawText(e.Graphics, e.Header.Text, Ui.SemiSmall, Rectangle.Inflate(e.Bounds, -Ui.P(8), 0), t.Mut, Align(e.Header.TextAlign));
        }

        protected override void OnDrawItem(DrawListViewItemEventArgs e) { }

        protected override void OnDrawSubItem(DrawListViewSubItemEventArgs e)
        {
            var t = Theme.T; var g = e.Graphics; var r = e.Bounds;
            using (var b = new SolidBrush(e.Item.Selected ? Theme.Mix(t.Card, t.Acc, t.Dark ? 0.22 : 0.14) : t.Card)) g.FillRectangle(b, r);
            using (var p = new Pen(t.Line)) g.DrawLine(p, r.Left, r.Bottom - 1, r.Right, r.Bottom - 1);
            string text = e.SubItem.Text ?? "";
            bool dim = e.Item.Name == "dim";
            var inner = Rectangle.Inflate(r, -Ui.P(8), 0);
            if (e.ColumnIndex == BadgeColumn && text.Length > 0) { Badge(g, text, inner); return; }
            if (TypeTags && e.ColumnIndex == 0)
            {
                string ext = Path.GetExtension(text).TrimStart('.').ToUpperInvariant();
                if (ext.Length > 4) ext = ext.Substring(0, 4);
                var tr = new Rectangle(inner.X, r.Y + (r.Height - Ui.P(16)) / 2, Ui.P(32), Ui.P(16));
                Ui.Smooth(g); Ui.FillRound(g, TagColor(ext), tr, Ui.P(3)); g.SmoothingMode = SmoothingMode.None;
                TextRenderer.DrawText(g, ext, Ui.Tag, tr, Color.White, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter |
                                                                       TextFormatFlags.NoPrefix | TextFormatFlags.NoPadding | TextFormatFlags.SingleLine);
                inner = new Rectangle(inner.X + Ui.P(40), inner.Y, inner.Width - Ui.P(40), inner.Height);
            }
            Color fg = dim ? t.Dim : e.ColumnIndex == MutedColumn ? t.Mut : t.Ink;
            TextRenderer.DrawText(g, text, Font, inner, fg, Align(Columns[e.ColumnIndex].TextAlign));
        }

        static Color TagColor(string ext)
        {
            switch (ext)
            {
                case "PS1": return Theme.C(0x2f6fd6);
                case "CMD": return Theme.C(0x5b6573);
                case "PY": return Theme.C(0x2f8f5b);
                case "MD": return Theme.C(0x8a5cc7);
                case "JSON": return Theme.C(0xb26a00);
                default: return Theme.C(0x5d6672);
            }
        }

        static void Badge(Graphics g, string text, Rectangle inner)
        {
            var t = Theme.T;
            Color c = text == "delivered" || text == "running" ? t.Ok : text == "pending" ? t.Warn : t.Mut;
            int w = Ui.TextW(text, Ui.SemiSmall) + Ui.P(18), h = Ui.P(20);
            var br = new RectangleF(inner.X, inner.Y + (inner.Height - h) / 2f, Math.Min(w, inner.Width), h);
            Ui.Smooth(g); Ui.FillRound(g, Theme.Mix(t.Card, c, t.Dark ? 0.18 : 0.12), br, h / 2f); g.SmoothingMode = SmoothingMode.None;
            TextRenderer.DrawText(g, text, Ui.SemiSmall, Rectangle.Round(br), c,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix | TextFormatFlags.SingleLine);
        }
    }

    sealed class ThemedCombo : ComboBox
    {
        public ThemedCombo()
        {
            DropDownStyle = ComboBoxStyle.DropDownList; DrawMode = DrawMode.OwnerDrawFixed; FlatStyle = FlatStyle.Flat;
            Font = Ui.Body; ItemHeight = Math.Min(255, Ui.P(22));
        }
        protected override void OnDrawItem(DrawItemEventArgs e)
        {
            var t = Theme.T;
            bool sel = (e.State & DrawItemState.Selected) != 0 && (e.State & DrawItemState.ComboBoxEdit) == 0;
            using (var b = new SolidBrush(sel ? Theme.Mix(t.Input, t.Acc, 0.3) : t.Input)) e.Graphics.FillRectangle(b, e.Bounds);
            if (e.Index >= 0)
                TextRenderer.DrawText(e.Graphics, GetItemText(Items[e.Index]), Font, Rectangle.Inflate(e.Bounds, -Ui.P(4), 0), t.Ink, Ui.Line);
        }
    }

    sealed class MenuRenderer : ToolStripProfessionalRenderer
    {
        protected override void OnRenderToolStripBackground(ToolStripRenderEventArgs e)
        {
            using (var b = new SolidBrush(Theme.T.Card)) e.Graphics.FillRectangle(b, e.AffectedBounds);
        }
        protected override void OnRenderToolStripBorder(ToolStripRenderEventArgs e)
        {
            using (var p = new Pen(Theme.T.Line)) e.Graphics.DrawRectangle(p, 0, 0, e.ToolStrip.Width - 1, e.ToolStrip.Height - 1);
        }
        protected override void OnRenderImageMargin(ToolStripRenderEventArgs e)
        {
            using (var b = new SolidBrush(Theme.T.Card)) e.Graphics.FillRectangle(b, e.AffectedBounds);
        }
        protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e)
        {
            var t = Theme.T;
            using (var b = new SolidBrush(e.Item.Selected ? Theme.Mix(t.Card, t.Acc, 0.22) : t.Card))
                e.Graphics.FillRectangle(b, new Rectangle(Point.Empty, e.Item.Size));
        }
        protected override void OnRenderItemText(ToolStripItemTextRenderEventArgs e) { e.TextColor = Theme.T.Ink; base.OnRenderItemText(e); }
    }

    // ====================================================================== main window
    sealed class MainForm : Form
    {
        readonly string root;
        readonly RichTextBox output = new RichTextBox();
        readonly System.Windows.Forms.Timer statusTimer = new System.Windows.Forms.Timer();
        readonly System.Windows.Forms.Timer logTimer = new System.Windows.Forms.Timer();
        readonly System.Windows.Forms.Timer spinTimer = new System.Windows.Forms.Timer();
        readonly System.Windows.Forms.Timer toastTimer = new System.Windows.Forms.Timer();
        readonly Toggle chkSync = new Toggle("With sync", true, Ui.P(40));
        readonly Toggle chkSyncOverview = new Toggle("With sync", true, Ui.P(32));
        readonly ThemedCombo cboProduct = new ThemedCombo();
        readonly ThemedList lvGifts = new ThemedList(), lvFiles = new ThemedList(), lvServices = new ThemedList(), lvRecent = new ThemedList();
        readonly ThemedCombo cboLog = new ThemedCombo();
        readonly RichTextBox logView = new RichTextBox();
        readonly Toggle chkFollow = new Toggle("Follow (refresh every 2 s)", true, Ui.P(32));
        readonly Toggle chkWrap = new Toggle("Wrap", false, Ui.P(32));
        readonly TextBox txtHighlight = new TextBox(), txtFileFilter = new TextBox();
        readonly Hint logInfo = new Hint("");
        readonly NumericUpDown numGold = new NumericUpDown(), numMoney = new NumericUpDown(), numMDollars = new NumericUpDown();
        readonly TextBox txtCars = new TextBox(), txtMessage = new TextBox();
        readonly ToolTip tips = new ToolTip();
        readonly ContextMenuStrip fileMenu = new ContextMenuStrip();
        volatile bool adbBusy;
        int running;

        // new UI parts
        HeaderBar header; Rail rail; Panel host; SplitContainer split; DockBar dockBar; Toast toast; FeedList feed;
        StateLine ovServer, ovEmu; ServiceTiles tiles; Banner serverBanner; Page emuPage; Card giftsCard;
        UiButton btnCollapse; readonly List<UiButton> startButtons = new List<UiButton>();
        readonly Dictionary<string, Page> pages = new Dictionary<string, Page>();
        readonly Dictionary<string, UiButton> giftChips = new Dictionary<string, UiButton>();
        string currentPage = "";
        bool dockCollapsed; int dockSaved;
        string lastStarted = "", lastFinished = "Ready";
        string toastLog = "sync.log";

        // live status (from PID files + listening ports, and adb get-state)
        sealed class Svc { public string Key, Short, Name, Addr, Log; public bool On; public int Pid; public DateTime Since; }
        readonly Svc[] svcs =
        {
            new Svc { Key = "dns", Short = "DNS", Name = "DNS logger", Addr = "127.0.0.1 (udp 53)", Log = "dns.err.log" },
            new Svc { Key = "cdn", Short = "CDN :8780", Name = "CDN (recorder_server)", Addr = "127.0.0.1:8780", Log = "cdn.err.log" },
            new Svc { Key = "sync", Short = "Sync :8781", Name = "Sync (retr0_local_service)", Addr = "127.0.0.1:8781", Log = "sync.log" },
        };
        bool statusKnown, emuKnown, emuOn; string emuState = "";
        DateTime lastServerCommand = DateTime.MinValue, stoppedAt = DateTime.MinValue;

        // gifts
        sealed class GiftRow { public long Id; public string Status, Product, Reward, Queued, Delivered, Note; }
        List<GiftRow> gifts = new List<GiftRow>();
        string giftFilter = "all";
        DateTime giftStamp = DateTime.MinValue;
        Dictionary<long, string> giftSeen;

        // files and logs
        readonly List<string[]> fileRows = new List<string[]>();
        string lastLogKey;

        // Store catalogue currency packages (the owner's seed data, STORE_PRESERVATION_GRANTS.md SP-06). The server
        // re-checks every id against the catalogue and takes the amount from there; this list is only the menu.
        static readonly Product[] Products = {
            new Product(10051, "Gold", 16), new Product(10052, "Gold", 42), new Product(10053, "Gold", 87),
            new Product(10054, "Gold", 183), new Product(10055, "Gold", 476), new Product(10056, "Gold", 1019),
            new Product(10045, "R$", 50000), new Product(10046, "R$", 140000), new Product(10047, "R$", 300000),
            new Product(10048, "R$", 700000), new Product(10049, "R$", 2000000), new Product(10050, "R$", 5000000),
            new Product(10461, "M$", 45000), new Product(10462, "M$", 115000), new Product(10463, "M$", 250000),
            new Product(10464, "M$", 520000), new Product(10465, "M$", 1350000), new Product(10466, "M$", 3000000),
        };

        public MainForm(string root)
        {
            this.root = root;
            Text = "RETR0 Server";
            Font = Ui.Body;
            AutoScaleMode = AutoScaleMode.None;   // sizes are already scaled by Ui.P
            var wa = Screen.PrimaryScreen.WorkingArea;
            Size = new Size(Math.Min(Ui.P(1180), wa.Width), Math.Min(Ui.P(800), wa.Height));
            MinimumSize = new Size(Math.Min(Ui.P(900), wa.Width), Math.Min(Ui.P(600), wa.Height));
            StartPosition = FormStartPosition.CenterScreen;
            var logo = LoadLogo();
            var icon = MakeIcon(logo);
            if (icon != null) Icon = icon;
            else try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            header = new HeaderBar(logo);
            header.ThemeButton.Click += delegate { ApplyTheme(!Theme.T.Dark); };
            tips.SetToolTip(header.ThemeButton, "Switch light / dark theme");
            Controls.Add(BuildBody());
            Controls.Add(header);

            statusTimer.Interval = 4000;
            statusTimer.Tick += delegate { RefreshStatus(); };
            statusTimer.Start();
            logTimer.Interval = 2000;
            logTimer.Tick += delegate { if (chkFollow.Checked && currentPage == "lg") LoadLog(); };
            logTimer.Start();
            spinTimer.Interval = 70;
            spinTimer.Tick += delegate { dockBar.Angle = (dockBar.Angle + 24) % 360; dockBar.Invalidate(); };
            toastTimer.Interval = 30000;
            toastTimer.Tick += delegate { HideToast(); };

            ApplyColors();
            ShowPage("ov");
            Shown += delegate
            {
                ApplyNativeTheme();
                try
                {
                    split.Panel1MinSize = Ui.P(240);
                    split.Panel2MinSize = dockBar.Height;
                    split.SplitterDistance = Math.Max(split.Panel1MinSize, split.Height - split.SplitterWidth - Ui.P(170));
                }
                catch { }
                RefreshStatus();
                Log("RETR0 Server control panel. Folder: " + root);
                Feed("Control panel opened", FeedKind.Quiet);
                UpdateDock();
            };
        }

        // ------------------------------------------------------------------ layout
        Control BuildBody()
        {
            split = new SplitContainer { Dock = DockStyle.Fill, Orientation = Orientation.Horizontal, FixedPanel = FixedPanel.Panel2,
                                         SplitterWidth = Math.Max(4, Ui.P(5)), TabStop = false };
            host = new Panel { Dock = DockStyle.Fill };
            rail = new Rail(root);
            split.Panel1.Controls.Add(host);
            split.Panel1.Controls.Add(rail);

            AddPage("ov", "Overview", G.Overview, OverviewPage());
            AddPage("sv", "Server", G.Server, ServerPage());
            AddPage("em", "Emulator & client", G.Phone, ClientPage());
            AddPage("gf", "Gifts", G.Gift, GiftsPage());
            AddPage("fl", "Files", G.Folder, FilesPage());
            AddPage("lg", "Logs", G.Doc, LogsPage());

            toast = new Toast { Anchor = AnchorStyles.Bottom | AnchorStyles.Right };
            Btn(toast.Actions, "Restart server", G.Restart, BtnKind.Primary, delegate { HideToast(); ServerCommand("restart" + SyncArg(), "Restart server"); }).Margin = new Padding(0, 0, Ui.P(6), 0);
            Btn(toast.Actions, "Show log", null, BtnKind.Chip, delegate { HideToast(); ShowLog(toastLog); }).Margin = new Padding(0, 0, Ui.P(6), 0);
            Btn(toast.Actions, "Dismiss", null, BtnKind.Chip, delegate { HideToast(); });
            host.Controls.Add(toast);
            host.Resize += delegate { PlaceToast(); };

            dockBar = new DockBar();
            btnCollapse = Btn(dockBar.Buttons, "Collapse", G.Down, BtnKind.Chip, delegate { ToggleDock(); });
            Btn(dockBar.Buttons, "Clear", G.Clear, BtnKind.Chip, delegate { output.Clear(); });
            Btn(dockBar.Buttons, "Copy", G.Copy, BtnKind.Chip, delegate { try { if (output.TextLength > 0) Clipboard.SetText(output.Text); } catch { } });
            foreach (Control b in dockBar.Buttons.Controls) b.Margin = new Padding(Ui.P(6), 0, 0, 0);
            output.ReadOnly = true; output.WordWrap = false; output.ScrollBars = RichTextBoxScrollBars.Both; output.DetectUrls = false;
            output.Dock = DockStyle.Fill; output.Font = Ui.Mono; output.BorderStyle = BorderStyle.None;
            output.BackColor = Theme.ConBg; output.ForeColor = Theme.ConInk;
            var console = new Panel { Dock = DockStyle.Fill, BackColor = Theme.ConBg, Padding = new Padding(Ui.P(12), Ui.P(6), 0, 0) };
            console.Controls.Add(output);
            split.Panel2.Controls.Add(console);
            split.Panel2.Controls.Add(dockBar);
            return split;
        }

        void AddPage(string key, string title, string glyph, Page page)
        {
            pages[key] = page;
            host.Controls.Add(page);
            var nav = rail.Add(new NavButton(key, title, glyph));
            nav.Click += delegate { ShowPage(key); };
        }

        void ShowPage(string key)
        {
            if (currentPage == key) return;
            currentPage = key;
            foreach (var kv in pages) if (kv.Key != key) kv.Value.Visible = false;
            pages[key].Visible = true; pages[key].BringToFront();
            if (toast.Visible) toast.BringToFront();
            foreach (var n in rail.Items) n.Selected = n.Key == key;
            if (key == "gf") LoadGifts();
            if (key == "fl") LoadFiles();
            if (key == "lg") LoadLog();
        }

        static FlowLayoutPanel Flow()
        {
            return new FlowLayoutPanel { WrapContents = true, AutoSize = false, Margin = Padding.Empty, Padding = Padding.Empty };
        }

        static UiButton Btn(Control parent, string text, string glyph, BtnKind kind, EventHandler click, bool large = false)
        {
            var b = new UiButton(text, glyph, kind, large);
            if (click != null) b.Click += click;
            parent.Controls.Add(b);
            return b;
        }

        Page OverviewPage()
        {
            var p = new Page();
            p.AddRow(false, 12, new PageTitle("Overview", "Everything at a glance. Every button runs the same command as on its own screen."));

            var server = new Card("Server", "dns · cdn · sync");
            ovServer = server.Add(new StateLine());
            var f = server.Add(Flow());
            chkSyncOverview.Margin = new Padding(0, 0, Ui.P(14), Ui.P(8));
            f.Controls.Add(chkSyncOverview);
            chkSyncOverview.CheckedChanged += delegate { if (chkSync.Checked != chkSyncOverview.Checked) chkSync.Checked = chkSyncOverview.Checked; };
            ServerButtons(f, false);

            var emu = new Card("Emulator & game", null);
            ovEmu = emu.Add(new StateLine());
            var f2 = emu.Add(Flow());
            Btn(f2, "Play", G.Play, BtnKind.Primary, delegate { RunScript("client.cmd", "play", "Play"); });
            Btn(f2, "Client status", G.Info, BtnKind.Normal, delegate { RunScript("client.cmd", "status", "Client status"); });
            p.AddRow(false, 7, server, 5, emu);

            var services = new Card("Services", null);
            tiles = services.Add(new ServiceTiles());
            var sub = services.Add(new SubHeader("Recent gifts", "All gifts →"));
            sub.LinkClicked += delegate { ShowPage("gf"); };
            lvRecent.BadgeColumn = 1;
            lvRecent.Columns.Add("Gift", Ui.P(56), HorizontalAlignment.Right);
            lvRecent.Columns.Add("Status", Ui.P(100));
            lvRecent.Columns.Add("Reward", Ui.P(150));
            lvRecent.Columns.Add("Queued", Ui.P(130));
            lvRecent.DoubleClick += delegate { ShowPage("gf"); };
            services.Add(lvRecent); services.FillRow = lvRecent; services.FillMin = Ui.P(96);

            var activity = new Card("Activity", "this session");
            feed = activity.Add(new FeedList());
            activity.FillRow = feed; activity.FillMin = Ui.P(150);
            p.AddRow(true, 7, services, 5, activity);
            return p;
        }

        void ServerButtons(FlowLayoutPanel f, bool large)
        {
            startButtons.Add(Btn(f, "Start", G.Play, BtnKind.Go, delegate { ServerCommand("start" + SyncArg(), "Start server"); }, large));
            Btn(f, "Stop", G.Stop, BtnKind.Normal, delegate { ServerCommand("stop", "Stop server"); }, large);
            Btn(f, "Restart", G.Restart, BtnKind.Normal, delegate { ServerCommand("restart" + SyncArg(), "Restart server"); }, large);
            Btn(f, "Status", G.Info, BtnKind.Normal, delegate { ServerCommand("status", "Server status"); }, large);
        }

        Page ServerPage()
        {
            var p = new Page();
            p.AddRow(false, 12, new PageTitle("Server", "Three Python services in services\\ · 127.0.0.1 only"));

            var svc = new Card("Services (dns · cdn · sync)", null);
            var f = svc.Add(Flow());
            chkSync.Margin = new Padding(0, 0, Ui.P(18), Ui.P(8));
            f.Controls.Add(chkSync);
            chkSync.CheckedChanged += delegate { if (chkSyncOverview.Checked != chkSync.Checked) chkSyncOverview.Checked = chkSync.Checked; };
            ServerButtons(f, true);
            svc.Add(new Hint("Starts the three Python services in services\\ (127.0.0.1 only). Sync = the CloudCell replacement " +
                             "(gifts, cloud saves, racing codes). Edit a .py file, then Restart: no rebuild needed."));
            p.AddRow(false, 12, svc);

            var detail = new Card("Service detail", "from PID files and listening ports, every 4 s");
            lvServices.BadgeColumn = 1;
            lvServices.LastMin = Ui.P(76);
            lvServices.Columns.Add("Service", Ui.P(186));
            lvServices.Columns.Add("State", Ui.P(92));
            lvServices.Columns.Add("Address", Ui.P(136));
            lvServices.Columns.Add("PID", Ui.P(60), HorizontalAlignment.Right);
            lvServices.Columns.Add("Up since", Ui.P(76));
            foreach (var s in svcs)
            {
                var it = new ListViewItem(s.Name);
                it.SubItems.Add("…"); it.SubItems.Add(s.Addr); it.SubItems.Add(""); it.SubItems.Add("");
                lvServices.Items.Add(it);
            }
            lvServices.Height = Ui.P(26) * 4 + Ui.P(14);
            detail.Add(lvServices);

            var help = new Card("Help", null);
            var hf = help.Add(Flow());
            hf.FlowDirection = FlowDirection.TopDown; hf.WrapContents = false;
            Btn(hf, "Open OVERVIEW.md", G.OpenFile, BtnKind.Normal, delegate { OpenForEdit(Path.Combine(root, "OVERVIEW.md")); });
            Btn(hf, "Open README.md", G.OpenFile, BtnKind.Normal, delegate { OpenForEdit(Path.Combine(root, "README.md")); });
            Btn(hf, "Open server folder", G.OpenFolder, BtnKind.Normal, delegate { Explore(root); });
            help.Add(new Hint("The full guide is OVERVIEW.md in the server folder; README.md has the short version."));
            p.AddRow(false, 8, detail, 4, help);
            return p;
        }

        string SyncArg() { return chkSync.Checked ? " -WithSync" : ""; }

        void ServerCommand(string args, string title)
        {
            lastServerCommand = DateTime.Now;
            RunScript("retr0_server.cmd", args, title);
        }

        Page ClientPage()
        {
            var p = new Page();
            emuPage = p;
            p.AddRow(false, 12, new PageTitle("Emulator & client", "adb · client.cmd"));
            serverBanner = new Banner("The server is not running. Start it first (Server, With sync) before pressing Play.");
            p.AddRow(false, 12, serverBanner);
            p.SetHidden(serverBanner, true);

            var play = new Card("Play", null);
            var f1 = play.Add(Flow());
            Btn(f1, "Play", G.Play, BtnKind.Primary, delegate { RunScript("client.cmd", "play", "Play"); }, true);
            Btn(f1, "Client status", G.Info, BtnKind.Normal, delegate { RunScript("client.cmd", "status", "Client status"); }, true);
            Btn(f1, "adb devices", G.Devices, BtnKind.Normal, delegate { RunExe("adb", "devices -l", "adb devices"); }, true);
            play.Add(new Hint("Play = check the emulator runs the RETR0 client, set adb reverse 8780, start the game. " +
                              "Start the server first (Server, With sync)."));
            p.AddRow(false, 12, play);

            var install = new Card("Install", "keeps your progress");
            var f2 = install.Add(Flow());
            Btn(f2, "Apply client", G.Check, BtnKind.Normal, delegate { RunScript("client.cmd", "apply", "Apply client"); });
            Btn(f2, "Fix after emulator restart", G.Repair, BtnKind.Normal, delegate { RunScript("client.cmd", "fix-reboot", "Fix after emulator restart"); });
            install.Add(new Hint("Apply = swap in the RETR0 client in place. After an emulator restart the swapped APK is gone " +
                                 "(data is kept): use Fix after emulator restart."));

            var ui = new Card("Username button text", null);
            var f3 = ui.Add(Flow());
            Btn(f3, "Apply button text", G.Check, BtnKind.Normal, delegate { RunScript("client.cmd", "ui-text", "Apply button text"); });
            Btn(f3, "Restore button text", G.Undo, BtnKind.Normal, delegate { RunScript("client.cmd", "ui-text-restore", "Restore button text"); });
            ui.Add(new Hint("Renames Settings > ENTER RACING CODE to \"Change Username (Restart Required)\" (edits two of the " +
                            "game's UI files on the emulator; originals kept in backups\\ui_text)."));
            p.AddRow(false, 6, install, 6, ui);

            var danger = new Card("Danger zone", null) { Danger = true };
            danger.Add(new DangerRow("Restore original",
                "Puts the original 14.0.1 APK back. The RETR0 client is removed until you Apply client again.",
                new UiButton("Restore original", G.Undo, BtnKind.DangerOutline, false))).Controls[0].Click += delegate
                {
                    if (MessageBox.Show(this, "Put the original 14.0.1 APK back?\n\nThe RETR0 client is removed until you press " +
                        "Apply client again. Your progress is kept.", "RETR0 Server", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
                        RunScript("client.cmd", "restore", "Restore original");
                };
            danger.Add(new DangerRow("New install (deletes data)",
                "Uninstalls the game and deletes its data and downloaded assets. Asks you to confirm, then opens a console that asks you to type YES.",
                new UiButton("New install...", G.Delete, BtnKind.Danger, false))).Controls[0].Click += delegate
                {
                    if (MessageBox.Show(this, "New install UNINSTALLS the game and deletes its data and downloaded assets.\n\n" +
                        "A console window opens and asks you to type YES. Continue?", "RETR0 Server",
                        MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes)
                        OpenConsole("client.cmd", "install-fresh");
                };
            p.AddRow(false, 12, danger);
            return p;
        }

        Page GiftsPage()
        {
            var p = new Page();
            p.AddRow(false, 12, new PageTitle("Gifts", "The game picks gifts up when it starts · gifts currently go to every connected game"));

            var cat = new Card("Catalogue gift", "store catalogue amounts only");
            var f = cat.Add(Flow());
            cboProduct.Width = Ui.P(340);
            foreach (var pr in Products) cboProduct.Items.Add(pr);
            cboProduct.SelectedIndex = 0;
            f.Controls.Add(cboProduct);
            var send = Btn(f, "Send gift", G.Send, BtnKind.Primary, delegate { SendGift(); });
            cboProduct.Margin = new Padding(0, Math.Max(0, (send.Height - cboProduct.Height) / 2), Ui.P(8), Ui.P(8));
            cat.Add(new Hint("Gold appears in Notifications (tap to claim); R$ and M$ are credited at once with a RETR0 popup."));

            var custom = new Card("Custom gift", "any amount, or cars by id");
            var cf = custom.Add(Flow());
            AddField(cf, "Gold", numGold, 1000000);
            AddField(cf, "R$", numMoney, 100000000);
            AddField(cf, "M$", numMDollars, 100000000);
            txtCars.BorderStyle = BorderStyle.FixedSingle; txtCars.Font = Ui.Body;
            txtMessage.BorderStyle = BorderStyle.FixedSingle; txtMessage.Font = Ui.Body;
            cf.Controls.Add(new FieldBox("Car ids", txtCars, Ui.P(90)));
            var msgBox = new FieldBox("Message", txtMessage, Ui.P(170));
            cf.Controls.Add(msgBox);
            var sendCustom = Btn(cf, "Send custom gift", G.Send, BtnKind.Primary, delegate { SendCustomGift(); });
            sendCustom.Margin = new Padding(0, Math.Max(0, msgBox.Height - sendCustom.Height), Ui.P(8), Ui.P(8));
            custom.Add(new Hint("Credited at once with a RETR0 popup the next time the game starts. Car ids are the game's car " +
                                "numbers (e.g. 383 = Audi e-tron FE06), several separated by commas. Leave a box at 0 to skip it."));
            p.AddRow(false, 5, cat, 7, custom);

            giftsCard = new Card("Gifts", "");
            var tb = giftsCard.Add(Flow());
            foreach (var k in new[] { "all", "pending", "delivered", "held" })
            {
                string key = k;
                var chip = Btn(tb, k, null, BtnKind.Chip, delegate { giftFilter = key; PopulateGifts(); });
                chip.Margin = new Padding(0, 0, Ui.P(6), Ui.P(8));
                giftChips[key] = chip;
            }
            var refresh = Btn(tb, "Refresh list", G.Restart, BtnKind.Chip, delegate { LoadGifts(); });
            refresh.Margin = new Padding(Ui.P(10), 0, 0, Ui.P(8));

            lvGifts.BadgeColumn = 1;
            foreach (var c in new[] { "Gift", "Status", "Product", "Reward", "Queued", "Delivered", "Source / note" })
                lvGifts.Columns.Add(c, c == "Reward" || c == "Source / note" ? Ui.P(220) : c == "Gift" || c == "Product" ? Ui.P(80) : Ui.P(130),
                                    c == "Gift" || c == "Product" ? HorizontalAlignment.Right : HorizontalAlignment.Left);
            giftsCard.Add(lvGifts); giftsCard.FillRow = lvGifts; giftsCard.FillMin = Ui.P(150);
            p.AddRow(true, 12, giftsCard);
            UpdateGiftChips();
            return p;
        }

        static void AddField(FlowLayoutPanel f, string label, NumericUpDown n, int max)
        {
            n.Maximum = max; n.Minimum = 0; n.ThousandsSeparator = true; n.Font = Ui.Body; n.BorderStyle = BorderStyle.FixedSingle;
            n.Increment = max >= 100000000 ? 10000 : 10;
            f.Controls.Add(new FieldBox(label, n, Ui.P(max >= 100000000 ? 118 : 92)));
        }

        Page FilesPage()
        {
            var p = new Page();
            p.AddRow(false, 12, new PageTitle("Files", "Double-click a file to edit it (it never runs) · restart the server afterwards"));
            var card = new Card(null, null);
            var f = card.Add(Flow());
            foreach (var d in new[] { "services", "tools", "config", "runtime", "backups", @"client\apk" })
            {
                string dir = d;
                Btn(f, dir + "\\", G.Folder, BtnKind.Chip, delegate { Explore(Path.Combine(root, dir)); }).Margin = new Padding(0, 0, Ui.P(6), Ui.P(8));
            }
            txtFileFilter.Width = Ui.P(200); txtFileFilter.BorderStyle = BorderStyle.FixedSingle; txtFileFilter.Font = Ui.Body;
            txtFileFilter.Margin = new Padding(Ui.P(10), Math.Max(0, (Ui.P(30) - txtFileFilter.Height) / 2), 0, Ui.P(8));
            txtFileFilter.TextChanged += delegate { ApplyFileFilter(); };
            f.Controls.Add(txtFileFilter);

            lvFiles.TypeTags = true; lvFiles.MutedColumn = 3;
            lvFiles.Columns.Add("File", Ui.P(400)); lvFiles.Columns.Add("Size", Ui.P(80), HorizontalAlignment.Right);
            lvFiles.Columns.Add("Modified", Ui.P(140)); lvFiles.Columns.Add("What", Ui.P(320));
            lvFiles.DoubleClick += delegate
            {
                if (lvFiles.SelectedItems.Count > 0) OpenForEdit(Path.Combine(root, lvFiles.SelectedItems[0].Text));
            };
            fileMenu.Items.Add("Edit", null, delegate { if (lvFiles.SelectedItems.Count > 0) OpenForEdit(Path.Combine(root, lvFiles.SelectedItems[0].Text)); });
            fileMenu.Items.Add("Show in folder", null, delegate { if (lvFiles.SelectedItems.Count > 0) ShowInFolder(Path.Combine(root, lvFiles.SelectedItems[0].Text)); });
            fileMenu.Renderer = new MenuRenderer();
            lvFiles.ContextMenuStrip = fileMenu;
            card.Add(lvFiles); card.FillRow = lvFiles; card.FillMin = Ui.P(200);
            p.AddRow(true, 12, card);
            return p;
        }

        Page LogsPage()
        {
            var p = new Page();
            p.AddRow(false, 12, new PageTitle("Logs", "Read-only view of runtime\\ · open it in your editor for the whole file"));
            var card = new Card(null, null);
            var f = card.Add(Flow());
            cboLog.Width = Ui.P(220);
            foreach (var n in new[] { "sync.log", "cdn.out.log", "cdn.err.log", "sync.err.log", "dns.out.log", "dns.err.log" })
                cboLog.Items.Add(n);
            cboLog.SelectedIndex = 0;
            cboLog.SelectedIndexChanged += delegate { LoadLog(); };
            cboLog.Margin = new Padding(0, Math.Max(0, (Ui.P(32) - cboLog.Height) / 2), Ui.P(14), Ui.P(8));
            f.Controls.Add(cboLog);
            f.Controls.Add(chkFollow);
            txtHighlight.Width = Ui.P(180); txtHighlight.BorderStyle = BorderStyle.FixedSingle; txtHighlight.Font = Ui.Body;
            txtHighlight.Margin = new Padding(0, Math.Max(0, (Ui.P(32) - txtHighlight.Height) / 2), Ui.P(14), Ui.P(8));
            txtHighlight.TextChanged += delegate { LoadLog(); };
            f.Controls.Add(txtHighlight);
            chkWrap.CheckedChanged += delegate { logView.WordWrap = chkWrap.Checked; };
            f.Controls.Add(chkWrap);
            Btn(f, "Open in editor", G.Edit, BtnKind.Normal, delegate { OpenForEdit(Path.Combine(root, "runtime", cboLog.Text)); });

            logView.ReadOnly = true; logView.ScrollBars = RichTextBoxScrollBars.Both; logView.WordWrap = false; logView.DetectUrls = false;
            logView.BorderStyle = BorderStyle.None; logView.Font = Ui.MonoSmall;
            logView.BackColor = Theme.ConBg; logView.ForeColor = Theme.ConInk;
            var logBox = new Panel { BackColor = Theme.ConBg, Padding = new Padding(Ui.P(10), Ui.P(6), 0, 0) };
            logView.Dock = DockStyle.Fill;
            logBox.Controls.Add(logView);
            card.Add(logBox); card.FillRow = logBox; card.FillMin = Ui.P(200);
            logInfo.Font = Ui.Small; logInfo.Text = " ";
            card.Add(logInfo);
            p.AddRow(true, 12, card);
            return p;
        }

        // ------------------------------------------------------------------ theme
        void ApplyTheme(bool dark)
        {
            Theme.T = dark ? Theme.DarkTheme : Theme.LightTheme;
            ApplyColors();
            ApplyNativeTheme();
            Invalidate(true);
        }

        void ApplyColors()
        {
            var t = Theme.T;
            BackColor = t.Bg; ForeColor = t.Ink;
            header.BackColor = t.Hdr; header.ForeColor = t.Ink;
            rail.BackColor = t.Rail; rail.ForeColor = t.Ink;
            host.BackColor = t.Bg;
            split.BackColor = t.Line; split.Panel1.BackColor = t.Bg; split.Panel2.BackColor = t.Hdr;
            dockBar.BackColor = t.Hdr; dockBar.ForeColor = t.Ink;
            toast.BackColor = t.Card; toast.ForeColor = t.Ink;
            foreach (var p in pages.Values) { p.BackColor = t.Bg; p.ForeColor = t.Ink; }
            fileMenu.BackColor = t.Card; fileMenu.ForeColor = t.Ink;
            Walk(this);
        }

        static void Walk(Control parent)
        {
            var t = Theme.T;
            foreach (Control c in parent.Controls)
            {
                var card = c as Card;
                if (card != null) { card.BackColor = card.Danger ? Theme.Mix(t.Card, t.Bad, t.Dark ? 0.07 : 0.04) : t.Card; card.ForeColor = t.Ink; }
                else if (c is Hint) c.ForeColor = t.Mut;
                else if (c is TextBox || c is NumericUpDown || c is ComboBox) { c.BackColor = t.Input; c.ForeColor = t.Ink; }
                else if (c is ListView || c is ListBox) { c.BackColor = t.Card; c.ForeColor = t.Ink; }
                Walk(c);
            }
        }

        void ApplyNativeTheme()
        {
            if (!IsHandleCreated) return;
            bool dark = Theme.T.Dark;
            Native.DarkTitleBar(this, dark);
            foreach (Control c in new Control[] { lvGifts, lvFiles, lvServices, lvRecent, feed, output, logView })
                Native.Scrollbars(c, dark);
            foreach (var p in pages.Values) Native.Scrollbars(p, dark);
            Native.Cue(txtFileFilter, "Filter files…");
            Native.Cue(txtHighlight, "Highlight text…");
        }

        static Image LoadLogo()
        {
            try { return Image.FromStream(new MemoryStream(Convert.FromBase64String(LogoPng))); }   // the stream must stay open
            catch { return null; }
        }

        static Icon MakeIcon(Image logo)
        {
            if (logo == null) return null;
            try
            {
                var bmp = new Bitmap(64, 64);
                using (var g = Graphics.FromImage(bmp))
                {
                    g.Clear(Color.FromArgb(11, 14, 18));
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    float h = 62f * logo.Height / logo.Width;
                    g.DrawImage(logo, 1f, (64 - h) / 2f, 62f, h);
                }
                return Icon.FromHandle(bmp.GetHicon());
            }
            catch { return null; }
        }

        // ------------------------------------------------------------------ output dock
        void ToggleDock()
        {
            try
            {
                if (!dockCollapsed)
                {
                    dockSaved = split.SplitterDistance;
                    split.SplitterDistance = Math.Max(split.Panel1MinSize, split.Height - split.SplitterWidth - dockBar.Height);
                }
                else split.SplitterDistance = Math.Max(split.Panel1MinSize, Math.Min(dockSaved, split.Height - split.SplitterWidth - Ui.P(120)));
            }
            catch { }
            dockCollapsed = !dockCollapsed;
            btnCollapse.Text = dockCollapsed ? "Expand" : "Collapse";
            btnCollapse.Glyph = dockCollapsed ? G.Up : G.Down;
            btnCollapse.Fit();
        }

        void UpdateDock()
        {
            if (InvokeRequired) { try { BeginInvoke((Action)UpdateDock); } catch { } return; }
            bool busy = Thread.VolatileRead(ref running) > 0;
            dockBar.Busy = busy;
            dockBar.Status = busy ? "Running: " + lastStarted + (running > 1 ? "  (+" + (running - 1) + " more)" : "") : lastFinished;
            spinTimer.Enabled = busy;
            dockBar.Invalidate();
        }

        // ------------------------------------------------------------------ toast + activity
        void Feed(string text, FeedKind kind)
        {
            if (InvokeRequired) { try { BeginInvoke((Action<string, FeedKind>)Feed, text, kind); } catch { } return; }
            if (feed != null) feed.Push(new FeedItem { When = DateTime.Now, Text = text, Kind = kind });
        }

        void ShowToast(string title, string body, string log)
        {
            toast.Title = title; toast.Body = body; toastLog = log;
            PlaceToast();
            toast.Visible = true; toast.BringToFront(); toast.Invalidate();
            toastTimer.Stop(); toastTimer.Start();
        }

        void HideToast() { toastTimer.Stop(); toast.Visible = false; }

        void PlaceToast()
        {
            toast.Location = new Point(Math.Max(0, host.ClientSize.Width - toast.Width - Ui.P(18)),
                                       Math.Max(0, host.ClientSize.Height - toast.Height - Ui.P(18)));
        }

        void ShowLog(string name)
        {
            ShowPage("lg");
            int i = cboLog.Items.IndexOf(name);
            if (i >= 0 && cboLog.SelectedIndex != i) cboLog.SelectedIndex = i; else LoadLog();
        }

        // ------------------------------------------------------------------ status
        void RefreshStatus()
        {
            var tcp = new HashSet<int>(IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners()
                                       .Where(e => IPAddress.IsLoopback(e.Address) || e.Address.Equals(IPAddress.Any)).Select(e => e.Port));
            var udp = new HashSet<int>(IPGlobalProperties.GetIPGlobalProperties().GetActiveUdpListeners()
                                       .Where(e => IPAddress.IsLoopback(e.Address) || e.Address.Equals(IPAddress.Any)).Select(e => e.Port));
            bool wasRunning = svcs[0].On && svcs[1].On;
            bool expected = (DateTime.Now - lastServerCommand).TotalSeconds < 30;
            var unexpected = new List<Svc>();
            foreach (var s in svcs)
            {
                int pid = AlivePid(s.Key);
                bool on = pid > 0 && (s.Key == "dns" ? udp.Contains(53) : tcp.Contains(s.Key == "cdn" ? 8780 : 8781));
                if (on && (!s.On || s.Pid != pid))
                {
                    s.Since = DateTime.Now;
                    try { s.Since = Process.GetProcessById(pid).StartTime; } catch { }
                }
                if (statusKnown && s.On && !on && !expected) unexpected.Add(s);
                s.On = on; s.Pid = on ? pid : 0;
            }
            bool nowRunning = svcs[0].On && svcs[1].On;
            if (statusKnown && wasRunning && !nowRunning) { stoppedAt = DateTime.Now; if (unexpected.Count == 0) Feed("Server stopped", FeedKind.Quiet); }
            if (statusKnown && !wasRunning && nowRunning) Feed("Server running" + (svcs[2].On ? " with sync" : " without sync"), FeedKind.Good);
            foreach (var s in unexpected) Feed(s.Short + " stopped unexpectedly", FeedKind.Bad);
            if (unexpected.Count == 1)
                ShowToast(unexpected[0].Short + " stopped unexpectedly", DateTime.Now.ToString("HH:mm") + " · it was running a moment ago. " +
                          "See " + unexpected[0].Log + ".", unexpected[0].Log);
            else if (unexpected.Count > 1)
                ShowToast(unexpected.Count + " services stopped unexpectedly", DateTime.Now.ToString("HH:mm") + " · " +
                          string.Join(", ", unexpected.Select(s => s.Short)) + ". See their logs.", unexpected[0].Log);
            statusKnown = true;

            if (!adbBusy)
            {
                adbBusy = true;
                ThreadPool.QueueUserWorkItem(delegate
                {
                    string state = RunCapture("adb", "get-state", 3000);
                    bool ok = state != null && state.Trim() == "device";
                    string text = state == null ? "no adb / no device" : state.Trim().Length == 0 ? "no device" : state.Trim();
                    try { BeginInvoke((Action)delegate { SetEmulator(ok, text); }); } catch { }
                    adbBusy = false;
                });
            }
            UpdateStatusViews();
            LoadGiftsIfChanged();
        }

        void SetEmulator(bool ok, string state)
        {
            if (emuKnown && ok != emuOn) Feed(ok ? "Emulator connected" : "Emulator disconnected", ok ? FeedKind.Good : FeedKind.Quiet);
            emuKnown = true; emuOn = ok; emuState = state;
            UpdateStatusViews();
        }

        int AlivePid(string name)
        {
            try
            {
                int pid = int.Parse(File.ReadAllText(Path.Combine(root, "runtime", name + ".pid")).Trim());
                return Process.GetProcessById(pid).HasExited ? 0 : pid;
            }
            catch { return 0; }
        }

        bool PidAlive(string name) { return AlivePid(name) > 0; }

        static string Ago(TimeSpan d)
        {
            if (d.TotalMinutes < 1) return "less than a minute";
            if (d.TotalHours < 1) return (int)d.TotalMinutes + " min";
            if (d.TotalDays < 1) return (int)d.TotalHours + " h " + d.Minutes + " min";
            return (int)d.TotalDays + " d " + d.Hours + " h";
        }

        void UpdateStatusViews()
        {
            var t = Theme.T;
            bool dns = svcs[0].On, cdn = svcs[1].On, sync = svcs[2].On, running = dns && cdn, any = dns || cdn || sync;
            DateTime since = running ? (svcs[0].Since < svcs[1].Since ? svcs[0].Since : svcs[1].Since) : DateTime.Now;
            string up = Ago(DateTime.Now - since);

            header.Known = statusKnown; header.EmuKnown = emuKnown;
            header.Lights[0] = dns; header.Lights[1] = cdn; header.Lights[2] = sync; header.Lights[3] = emuOn;
            string missing = string.Join(", ", svcs.Where(s => !s.On).Select(s => s.Short));
            if (!statusKnown) { header.PillText = "Checking…"; header.PillDetail = ""; header.PillColor = t.Dim; }
            else if (running) { header.PillText = "Server running"; header.PillDetail = "· up " + up + (sync ? " · with sync" : " · without sync"); header.PillColor = t.Ok; }
            else if (any) { header.PillText = "Server partly running"; header.PillDetail = "· not running: " + missing; header.PillColor = t.Warn; }
            else { header.PillText = "Server stopped"; header.PillDetail = stoppedAt != DateTime.MinValue ? "· stopped " + stoppedAt.ToString("HH:mm") : ""; header.PillColor = t.Bad; }
            header.Invalidate();

            if (running) ovServer.Set(t.Ok, "Running", "since " + since.ToString("HH:mm") + " · up " + up + (sync ? " · with sync" : " · without sync"));
            else if (any) ovServer.Set(t.Warn, "Partly running", "not running: " + missing);
            else ovServer.Set(statusKnown ? t.Bad : t.Dim, statusKnown ? "Stopped" : "Checking…", statusKnown ? "Start it before playing" : "");
            ovEmu.Set(!emuKnown ? t.Dim : emuOn ? t.Ok : t.Bad, !emuKnown ? "Checking…" : emuOn ? "Connected" : "Not connected",
                      emuKnown ? "adb: " + emuState : "");

            tiles.Known = statusKnown;
            for (int i = 0; i < 3; i++)
            {
                var s = svcs[i];
                tiles.On[i] = s.On;
                string port = i == 1 ? ":8780" : i == 2 ? ":8781" : "";
                tiles.Detail[i] = s.On ? (port.Length > 0 ? port + " · " : "") + "pid " + s.Pid : (port.Length > 0 ? port + " closed" : "not running");
                var it = lvServices.Items[i];
                string state = !statusKnown ? "…" : s.On ? "running" : "stopped";
                string pid = s.On ? s.Pid.ToString() : "—", upSince = s.On ? s.Since.ToString("HH:mm") : "—";
                if (it.SubItems[1].Text != state) it.SubItems[1].Text = state;
                if (it.SubItems[3].Text != pid) it.SubItems[3].Text = pid;
                if (it.SubItems[4].Text != upSince) it.SubItems[4].Text = upSince;
            }
            tiles.On[3] = emuOn; tiles.Detail[3] = emuKnown ? "adb: " + emuState : "checking…";
            tiles.Invalidate();

            foreach (var b in startButtons) b.Kind = running ? BtnKind.Normal : BtnKind.Go;
            emuPage.SetHidden(serverBanner, !statusKnown || running);
        }

        // ------------------------------------------------------------------ running things
        void Log(string line)
        {
            if (InvokeRequired) { try { BeginInvoke((Action<string>)Log, line); } catch { } return; }
            Color c = Theme.ConInk;
            if (line.StartsWith("> ")) c = Theme.ConCmd;
            else if (line.StartsWith("! ")) c = Theme.ConErr;
            else if (line.StartsWith("< ")) c = line.Contains("(exit 0)") ? Theme.ConOk : Theme.ConErr;
            output.SelectionStart = output.TextLength;
            output.SelectionLength = 0;
            output.SelectionColor = c;
            output.AppendText(line + "\n");
            output.SelectionStart = output.TextLength;
            output.ScrollToCaret();
        }

        // Runs one of the package's .cmd wrappers (retr0_server.cmd, client.cmd) through cmd.exe.
        void RunScript(string script, string args, string title)
        {
            Start("cmd.exe", "/c \"\"" + Path.Combine(root, script) + "\" " + args + "\"", title);
        }

        void RunExe(string exe, string args, string title) { Start(exe, args, title); }

        void Start(string exe, string args, string title)
        {
            Log("");
            Log("> " + title + "   [" + DateTime.Now.ToString("HH:mm:ss") + "]");
            bool serverScript = args.IndexOf("retr0_server.cmd", StringComparison.OrdinalIgnoreCase) >= 0;
            var psi = new ProcessStartInfo(exe, args)
            {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            try
            {
                var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
                var clock = Stopwatch.StartNew();
                p.OutputDataReceived += (s, e) => { if (e.Data != null) Log(e.Data); };
                p.ErrorDataReceived += (s, e) => { if (e.Data != null && e.Data.Trim().Length > 0) Log("! " + e.Data); };
                // The server services inherit the output pipe and keep it open after the script ends, so "done" is
                // reported when the script process exits, not when its output closes.
                p.Exited += delegate
                {
                    int code = -1; try { code = p.ExitCode; } catch { }
                    double secs = clock.Elapsed.TotalSeconds;
                    Interlocked.Decrement(ref running);
                    if (serverScript) lastServerCommand = DateTime.Now;
                    Log("< " + title + " finished (exit " + code + ")   " + secs.ToString("0.0") + " s");
                    Feed(title + " finished · exit " + code + " · " + secs.ToString("0.0") + " s", code == 0 ? FeedKind.Good : FeedKind.Bad);
                    lastFinished = "Last: " + title + " · exit " + code + " · " + secs.ToString("0.0") + " s · " + DateTime.Now.ToString("HH:mm:ss");
                    UpdateDock();
                    try { BeginInvoke((Action)RefreshStatus); } catch { }
                };
                p.Start();
                Interlocked.Increment(ref running);
                lastStarted = title;
                UpdateDock();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
            }
            catch (Exception e) { Log("! could not start " + exe + ": " + e.Message); Feed("Could not start " + title, FeedKind.Bad); }
        }

        // Interactive commands (install-fresh asks for YES) run in their own console window.
        void OpenConsole(string script, string args)
        {
            Feed("Opened console: " + script + " " + args, FeedKind.Info);
            Process.Start(new ProcessStartInfo("cmd.exe", "/k \"\"" + Path.Combine(root, script) + "\" " + args + "\"")
                { WorkingDirectory = root, UseShellExecute = true });
        }

        static string RunCapture(string exe, string args, int timeoutMs)
        {
            try
            {
                var p = Process.Start(new ProcessStartInfo(exe, args)
                    { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true });
                string s = p.StandardOutput.ReadToEnd();
                if (!p.WaitForExit(timeoutMs)) { try { p.Kill(); } catch { } return null; }
                return s;
            }
            catch { return null; }
        }

        void OpenForEdit(string path)
        {
            if (!File.Exists(path)) { Log("! not found: " + path); return; }
            // Never "open" a .py/.ps1/.cmd: that would RUN it. Use the "edit" verb, else Notepad.
            try { Process.Start(new ProcessStartInfo(path) { Verb = "edit", UseShellExecute = true }); }
            catch { Process.Start("notepad.exe", "\"" + path + "\""); }
        }

        void Explore(string dir)
        {
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
            Process.Start("explorer.exe", "\"" + dir + "\"");
        }

        static void ShowInFolder(string path) { Process.Start("explorer.exe", "/select,\"" + path + "\""); }

        // ------------------------------------------------------------------ gifts
        void SendCustomGift()
        {
            var query = new List<string>();
            var parts = new List<string>();
            if (numGold.Value > 0) { query.Add("gold=" + (long)numGold.Value); parts.Add(((long)numGold.Value).ToString("N0") + " Gold"); }
            if (numMoney.Value > 0) { query.Add("money=" + (long)numMoney.Value); parts.Add(((long)numMoney.Value).ToString("N0") + " R$"); }
            if (numMDollars.Value > 0) { query.Add("mdollars=" + (long)numMDollars.Value); parts.Add(((long)numMDollars.Value).ToString("N0") + " M$"); }
            foreach (var s in txtCars.Text.Split(new[] { ',', ';', ' ' }, StringSplitOptions.RemoveEmptyEntries))
            {
                int id;
                if (!int.TryParse(s.Trim(), out id) || id <= 0) { MessageBox.Show(this, "Car ids must be whole numbers, e.g. 383", "Custom gift"); return; }
                query.Add("car=" + id); parts.Add("car #" + id);
            }
            if (query.Count == 0) { MessageBox.Show(this, "Enter an amount or a car id first.", "Custom gift"); return; }
            if (txtMessage.Text.Trim().Length > 0) query.Add("message=" + Uri.EscapeDataString(txtMessage.Text.Trim()));
            if (MessageBox.Show(this, "Send " + string.Join(", ", parts) + "?\n\nCredited at once with a RETR0 popup the next " +
                "time the game starts.", "Custom gift", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            PostGift(string.Join("&", query), string.Join(", ", parts));
        }

        void PostGift(string query, string what)
        {
            Log("");
            Log("> Send gift: " + what);
            try
            {
                using (var wc = new WebClient())
                    Log("  queued: " + wc.UploadString("http://127.0.0.1:8781/retr0/admin/gift?" + query, ""));
                Feed("Gift sent: " + what, FeedKind.Accent);
            }
            catch (WebException e)
            {
                string body = "";
                if (e.Response != null) using (var sr = new StreamReader(e.Response.GetResponseStream())) body = sr.ReadToEnd();
                Log("! refused: " + e.Message + (body.Length > 0 ? " - " + body : "") +
                    (e.Response == null ? "  (is the server running with sync?)" : ""));
                Feed("Gift refused: " + what, FeedKind.Bad);
            }
            LoadGifts();
        }

        void SendGift()
        {
            var p = (Product)cboProduct.SelectedItem;
            if (MessageBox.Show(this, string.Format("Send {0:N0} {1} (product {2})?\n\nThe game receives it the next time it " +
                "starts. Gold: claim it from Notifications. R$/M$: credited at once with a popup.", p.Amount, p.Currency, p.Id),
                "Send gift", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            PostGift("product=" + p.Id, string.Format("{0:N0} {1} (product {2})", p.Amount, p.Currency, p.Id));
        }

        string GiftsPath { get { return Path.Combine(root, @"runtime\sync_data\state.json"); } }

        // Re-read state.json only when it changed (checked with the 4 s status refresh), for the badge and Overview.
        void LoadGiftsIfChanged()
        {
            try
            {
                var stamp = File.Exists(GiftsPath) ? File.GetLastWriteTimeUtc(GiftsPath) : DateTime.MinValue;
                if (stamp != giftStamp) LoadGifts(true);
            }
            catch { }
        }

        void LoadGifts() { LoadGifts(false); }

        void LoadGifts(bool quiet)
        {
            string path = GiftsPath;
            var rows = new List<GiftRow>();
            try
            {
                giftStamp = File.Exists(path) ? File.GetLastWriteTimeUtc(path) : DateTime.MinValue;
                string json;
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var sr = new StreamReader(fs)) json = sr.ReadToEnd();
                var state = (Dictionary<string, object>)new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.DeserializeObject(json);
                object giftsObj;
                if (state.TryGetValue("gifts", out giftsObj))
                {
                    var all = (Dictionary<string, object>)giftsObj;
                    var raw = new List<KeyValuePair<string, Dictionary<string, object>>>();
                    foreach (var status in new[] { "pending", "claimed", "held" })
                    {
                        object list;
                        if (all.TryGetValue(status, out list) && list is IEnumerable)
                            foreach (var g in (IEnumerable)list)
                                raw.Add(new KeyValuePair<string, Dictionary<string, object>>(status, (Dictionary<string, object>)g));
                    }
                    foreach (var kv in raw.OrderByDescending(x => Convert.ToInt64(Get(x.Value, "id", 0))))
                    {
                        var g = kv.Value;
                        string msg = Convert.ToString(Get(g, "message", ""));
                        string note = Convert.ToString(Get(g, "note", ""));
                        rows.Add(new GiftRow
                        {
                            Id = Convert.ToInt64(Get(g, "id", 0)),
                            Status = kv.Key == "claimed" ? "delivered" : kv.Key,
                            Product = Convert.ToString(Get(g, "product_id", "")),
                            Reward = msg.Length > 0 ? msg.Replace("Preservation grant: ", "")
                                : Convert.ToString(Get(g, "metadata", "")).Split(new[] { ", displayImage" }, StringSplitOptions.None)[0],
                            Queued = When(Get(g, "queued", null)),
                            Delivered = When(Get(g, "claimed", null)),
                            Note = Convert.ToString(Get(g, "source", "")) + (note.Length > 0 ? " - " + note : "")
                        });
                    }
                }
            }
            catch (FileNotFoundException) { }
            catch (DirectoryNotFoundException) { }
            catch (Exception e) { if (!quiet) Log("! could not read gifts: " + e.Message); return; }

            // activity feed: new gifts and status changes since the last read
            if (giftSeen != null)
                foreach (var g in rows)
                {
                    string old;
                    if (!giftSeen.TryGetValue(g.Id, out old)) Feed("Gift #" + g.Id + " queued · " + g.Reward, FeedKind.Accent);
                    else if (old != g.Status) Feed("Gift #" + g.Id + " " + g.Status + " · " + g.Reward, g.Status == "delivered" ? FeedKind.Good : FeedKind.Quiet);
                }
            giftSeen = rows.ToDictionary(g => g.Id, g => g.Status);
            gifts = rows;
            PopulateGifts();
        }

        static ListViewItem GiftItem(GiftRow g, bool full)
        {
            var it = new ListViewItem(g.Id.ToString());
            it.SubItems.Add(g.Status);
            if (full) it.SubItems.Add(g.Product);
            it.SubItems.Add(g.Reward);
            it.SubItems.Add(g.Queued);
            if (full) { it.SubItems.Add(g.Delivered); it.SubItems.Add(g.Note); }
            it.ToolTipText = g.Reward + (g.Note.Length > 0 ? "\n" + g.Note : "");
            if (g.Status == "held") it.Name = "dim";
            return it;
        }

        void PopulateGifts()
        {
            lvGifts.BeginUpdate();
            lvGifts.Items.Clear();
            foreach (var g in gifts) if (giftFilter == "all" || g.Status == giftFilter) lvGifts.Items.Add(GiftItem(g, true));
            lvGifts.EndUpdate();
            lvGifts.FitLastColumn();
            lvRecent.BeginUpdate();
            lvRecent.Items.Clear();
            foreach (var g in gifts.Take(3)) lvRecent.Items.Add(GiftItem(g, false));
            lvRecent.EndUpdate();
            lvRecent.FitLastColumn();
            UpdateGiftChips();
        }

        void UpdateGiftChips()
        {
            int pending = gifts.Count(g => g.Status == "pending");
            foreach (var kv in giftChips)
            {
                int n = kv.Key == "all" ? gifts.Count : gifts.Count(g => g.Status == kv.Key);
                string text = char.ToUpper(kv.Key[0]) + kv.Key.Substring(1) + "  " + n;
                if (kv.Value.Text != text) { kv.Value.Text = text; kv.Value.Fit(); }
                kv.Value.Selected = kv.Key == giftFilter;
            }
            if (giftsCard != null) giftsCard.SetNote(gifts.Count + " total · " + pending + " pending");
            foreach (var n in rail.Items) if (n.Key == "gf") n.Badge = pending > 0 ? pending + " pending" : null;
        }

        static object Get(Dictionary<string, object> d, string k, object dflt)
        {
            object v; return d.TryGetValue(k, out v) && v != null ? v : dflt;
        }

        static string When(object unix)
        {
            if (unix == null) return "";
            try { return DateTimeOffset.FromUnixTimeSeconds(Convert.ToInt64(unix)).LocalDateTime.ToString("yyyy-MM-dd HH:mm"); }
            catch { return ""; }
        }

        // ------------------------------------------------------------------ files and logs
        static readonly Dictionary<string, string> About = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { @"services\dns_logger.py", "dns service: logs every lookup, answers none" },
            { @"services\recorder_server.py", "cdn service: asset packs, /time, forwards sync" },
            { @"services\local_service\retr0_local_service.py", "sync service: CloudCell replacement, gifts" },
            { @"services\cloudcell_codec\cloudcell_codec.py", "protocol codec used by the sync service" },
            { @"retr0_server.ps1", "start / stop / status of the services" },
            { @"retr0_server.cmd", "wrapper the panel uses for retr0_server.ps1" },
            { @"client.ps1", "client on the emulator: apply, restore, play, ui-text, fix-reboot" },
            { @"client.cmd", "wrapper the panel uses for client.ps1" },
            { @"tools\retr0_gui_patch.py", "username button text (client.ps1 ui-text)" },
            { @"config\rules_cdn_sync.json", "cdn routing rules (with sync)" },
            { @"config\rules_cdn.json", "cdn routing rules (assets only)" },
        };

        void LoadFiles()
        {
            fileRows.Clear();
            var files = new List<string>();
            foreach (var f in new[] { "retr0_server.ps1", "retr0_server.cmd", "client.ps1", "client.cmd", "play.cmd", "OVERVIEW.md", "README.md" })
                if (File.Exists(Path.Combine(root, f))) files.Add(f);
            foreach (var d in new[] { "services", "tools", "config" })
            {
                string dir = Path.Combine(root, d);
                if (!Directory.Exists(dir)) continue;
                foreach (var f in Directory.GetFiles(dir, "*", SearchOption.AllDirectories))
                {
                    string ext = Path.GetExtension(f).ToLowerInvariant();
                    if (f.Contains("__pycache__") || !new[] { ".py", ".ps1", ".cmd", ".json", ".md", ".s", ".c", ".ld", ".cs" }.Contains(ext)) continue;
                    files.Add(f.Substring(root.Length + 1));
                }
            }
            foreach (var rel in files)
            {
                var fi = new FileInfo(Path.Combine(root, rel));
                string what;
                fileRows.Add(new[] { rel, (fi.Length / 1024.0).ToString("0.0") + " KB", fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm"),
                                     About.TryGetValue(rel, out what) ? what : "" });
            }
            ApplyFileFilter();
        }

        void ApplyFileFilter()
        {
            string q = txtFileFilter.Text.Trim();
            lvFiles.BeginUpdate();
            lvFiles.Items.Clear();
            foreach (var r in fileRows)
            {
                if (q.Length > 0 && r[0].IndexOf(q, StringComparison.OrdinalIgnoreCase) < 0 && r[3].IndexOf(q, StringComparison.OrdinalIgnoreCase) < 0) continue;
                var it = new ListViewItem(r[0]);
                it.SubItems.Add(r[1]); it.SubItems.Add(r[2]); it.SubItems.Add(r[3]);
                it.ToolTipText = r[3].Length > 0 ? r[0] + "\n" + r[3] : r[0];
                lvFiles.Items.Add(it);
            }
            lvFiles.EndUpdate();
            lvFiles.FitLastColumn();
        }

        void LoadLog()
        {
            string path = Path.Combine(root, "runtime", cboLog.Text);
            string text; bool found = false;
            try
            {
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    long start = Math.Max(0, fs.Length - 96 * 1024);
                    fs.Seek(start, SeekOrigin.Begin);
                    using (var sr = new StreamReader(fs, Encoding.UTF8)) text = sr.ReadToEnd();
                    if (start > 0) { int nl = text.IndexOf('\n'); if (nl >= 0) text = text.Substring(nl + 1); }
                    found = true;
                }
            }
            catch (FileNotFoundException) { text = "(no " + cboLog.Text + " yet)"; }
            catch (DirectoryNotFoundException) { text = "(no " + cboLog.Text + " yet)"; }
            catch (Exception e) { text = "could not read: " + e.Message; }

            if (found)
            {
                try
                {
                    var fi = new FileInfo(path);
                    logInfo.Text = cboLog.Text + " · " + (fi.Length >= 1048576 ? (fi.Length / 1048576.0).ToString("0.0") + " MB" : (fi.Length / 1024.0).ToString("0.0") + " KB") +
                                   (chkFollow.Checked ? " · following" : " · paused") + " · last change " + fi.LastWriteTime.ToString("HH:mm:ss") +
                                   (fi.Length > 96 * 1024 ? " · showing the last 96 KB" : "");
                }
                catch { }
            }
            else logInfo.Text = " ";

            string hi = txtHighlight.Text.Trim();
            string key = cboLog.Text + "\u0001" + hi + "\u0001" + text;
            if (key == lastLogKey) return;
            lastLogKey = key;
            logView.Rtf = LogRtf(text, hi);
            logView.SelectionStart = logView.TextLength;
            logView.ScrollToCaret();
        }

        // The log is shown as RTF so timestamps can be dimmed and highlighted text coloured in one fast update.
        static string LogRtf(string text, string hi)
        {
            var sb = new StringBuilder(text.Length + text.Length / 8 + 512);
            sb.Append(@"{\rtf1\ansi\deff0{\fonttbl{\f0\fmodern ").Append(Ui.MonoSmall.Name).Append(";}}");
            sb.Append(@"{\colortbl ;").Append(Rgb(Theme.ConInk)).Append(Rgb(Theme.ConDim)).Append(Rgb(Theme.ConWarn)).Append("}");
            sb.Append(@"\f0\fs").Append((int)Math.Round(Ui.MonoSmall.SizeInPoints * 2)).Append(@"\cf1 ");
            var lines = text.Replace("\r\n", "\n").Split('\n');
            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i];
                int ts = StampLength(line);
                if (ts > 0) { sb.Append(@"\cf2 "); Esc(sb, line.Substring(0, ts)); sb.Append(@"\cf1 "); line = line.Substring(ts); }
                if (hi.Length == 0) Esc(sb, line);
                else
                {
                    int at = 0;
                    while (true)
                    {
                        int k = line.IndexOf(hi, at, StringComparison.OrdinalIgnoreCase);
                        if (k < 0) { Esc(sb, line.Substring(at)); break; }
                        Esc(sb, line.Substring(at, k - at));
                        sb.Append(@"\cf3\b "); Esc(sb, line.Substring(k, hi.Length)); sb.Append(@"\b0\cf1 ");
                        at = k + hi.Length;
                    }
                }
                if (i < lines.Length - 1) sb.Append(@"\par ");
            }
            sb.Append('}');
            return sb.ToString();
        }

        // "2026-11-20 13:14:13,245" at the start of a line
        static int StampLength(string s)
        {
            if (s.Length >= 23 && char.IsDigit(s[0]) && s[4] == '-' && s[7] == '-' && s[10] == ' ' && s[13] == ':' && s[16] == ':') return 23;
            return 0;
        }

        static string Rgb(Color c) { return @"\red" + c.R + @"\green" + c.G + @"\blue" + c.B + ";"; }

        static void Esc(StringBuilder sb, string s)
        {
            foreach (char ch in s)
            {
                if (ch == '\\' || ch == '{' || ch == '}') sb.Append('\\').Append(ch);
                else if (ch == '\t') sb.Append(@"\tab ");
                else if (ch == '\r') { }
                else if (ch < 128) sb.Append(ch);
                else sb.Append(@"\u").Append((int)(short)ch).Append('?');
            }
        }

        // ------------------------------------------------------------------ logo (RETRO, white on transparent, 264x176 PNG)
        const string LogoPng =
"iVBORw0KGgoAAAANSUhEUgAAAQgAAACwCAYAAADzGPBTAAAjWUlEQVR42u2debBlV3Xef+vc+153q1tSd0styRqQDEhgcIlSEmyDAsZAETA2nk" +
            "QRYipQlcIGAtjGwURQxCEOxi7ANnFiEspDAhlkW7HBQS5sLIxlMIMAgRACNWhArblRt6Qent57956VP8469O6tvc9w733z+qpOve433HvuOWd/" +
            "e43fAofD4XA4HI4tCVWVLt9zOBz9IJuIJIbB51ERGfntdTicIFDVc4EzAQ2+/YCI3O+32OGYHMVGdytUdTdwLjAA5oChHReo6i53NxyOyTHcBJ" +
            "9h3iyhY8BdRnqPA04BtgFH/TY7HFuXINQIYiQix81iKDdTfMXhcIKYHmKuhBODw8EWj0EkGUJE/ZY6HE4QDofDCcLhcDhBOBwOJwiHw+EE4XA4" +
            "nCAcDocThMPhcIJwOBwOJwiHw+EE4XA4nCAcDocThMPhcIJwOBxOEA6HwwnC4XA4QTgcDicI1t/sC4fDwdaVnFPVgkpCrnS1KIfDCaImhnngfC" +
            "pVaqm+pY8A9zhROBxuQVwAnAGMagsCONX+f7+7Gw7HFiUIcyu2A8vAAWCBamrWWcAOv2UOBx6kNBwXkWPAksvZOxxOEERzQ4tg1oUThMPhBPHd" +
            "aVk+68LhcIJwOBxOEA6HwwliBV0O9TiEw+EEQYYInBwcDicIh8PhBOFwOJwgZuReOBwOJwggqIFwOBxOEF2tCrcsHA4niNZUp8PhcIJwOBxOEP" +
            "3cCXczHA63IBwOhxOEw+FwgsADlA6HE8QK1kJ4mtPhcIJwOBxOEExcbu1uhsPhBOFwOJwgvJHL4XCCcDgcThB4p6fD4QThhOBwOEGw3mIOLlrr" +
            "cDhBeIDS4XCCcBfD4cCnezscjj7T7aVLseBqjaQcrnPLQab8+0JVC7vw0+pTSNA0prO4QfYwFEC5RtZjmfj3erBqy/r6qupgBs168T0s18vM15" +
            "oQ6vMJzks7/G3tAehKfZ7hJo031AvviIiUK+Hm2IM71YNmfzteo2s8zvx7rTGOrtF4JVzVmpxn9PoTk0L4/KjqPHA6sBPYbutzGBDkIrAAHAKO" +
            "hc+2kcXMiWKzEkQBHAeeo6ovs4teBjtIn/ddAO4HDgD3ANeLyO31gzUJUaiqiIiq6m7gtcAP2MKQVYi/KDAAvgX8rn2mXwSembHcdBXvcwl8Gn" +
            "i/iCzatXol8EJgbsLXL4FH7XMeAO6we3j/ahNjbC3Yoj7LjnOBPUYO2+zzDuwQ+1rYOS8BR1T1gH2mW0VkIfUem93FiP+vPQjiCPAq4GUzPreH" +
            "VPVG4M+Bq0Tkvpoo+uxGdiP/6wqcXx88E7gV+Jfr6N5fATwVeLWq/hvg3SvwHveq6g3Ah0TkqtUih4AYdgKPBy4C9hohCCdrnyzZc1wTxND+Pz" +
            "QS2QM80X73YVXdD3xJRG6bJVFs9iDlgjHu2C70LHa83cCz7XiLqv4B8D4ROdjlpqhqISKlql4C/JidW7nKGaX6IbzcjuV1ktGq79NPGjlcYddm" +
            "ZOcnMxoA/T3AOcBHVfV8M9cPxwt5lsRgFuN24PuAJwCnRWQwDCyGQeAmFwFRDIL7NDbLaGgk8xzgclW9BfiEiOwPnzcniLwlURPDYEYLq7RD7S" +
            "F7G/AKVX2LiPyxqkrHh+y0yHSUNQgAj4NrU6yT+1Wf13ywSAYzuH91vGdo1uVrgE8CZwP7VHUPcG9tqs+SHGzjuAR4irm744AUiugZGCSIoYiO" +
            "YfDv2m1eMLfkMuBpqvp54MMicngakthIg3N0HZ3LwG5SvbtdCFylqu8HhvZQtF3bMjIr18KFK1aZnPqe4yxjIWr37Cjwr4HrjBxGtmD3AJeo6t" +
            "4o3TgtOZwG/DDwg8AOs9aIyEESRBH/P3zuwvs2jEhjyV7/ecCvquozanKY5DMVXjU5sSR/eBNrongNcLWq7jA3Qnq81lqNFdB1vCHojIimDgAv" +
            "AK8DPgHsC1yaOs07BzxRVc8Ndv5pyOF84PnAeUYMsYUg0fdCS66IrIphQCbh34U/C4nimLkev6Cqr7AYWe/P5O3e0xNYSBRLwEvMmpgHZNqdyM" +
            "vWp7aS1O7PopHDJ6myBmV0HYrg9y+alCQCcrgY+KfmKo0TrsEgEVuIXQjJfB1Ef5eyLoaBK/NS4M22cfX6TE4Qs110cwFJvM9MO+8hYU2DnoUF" +
            "834e+DhwZhB7kWDRhWtiDHyvqp7RZ0EF5PAU4OlRIdog2vklshJC4hhmgpODiADagplzgTXxbOBtqnpKn8/kBDF7zJk5+RpVvcJcDb/Oa2NBDI" +
            "wcXg9ca5bDKDLTJTL3Q+K4uN51e5DDJcDTgszQIJGhKBKWwCAiktTPyMQtUpmP0OWYs9jL04ErLZvSKSZRbKAmLVnBdF/O3+3rB4c7BMB7VXVf" +
            "dS+mJgmdcdwgzshoz3JrXcH7XibcOJnAclgA3gD8FVVAchyRQZEJCtbl3adQpSQbF1MUc7jMzj/lBsSLepj4vkRugzS4EanzLhLvWxPFMXN7Xm" +
            "+kJ25B9A9mlfZ1FPxbe5JFbaY+DnhD15vRAWV0XtMco+CBG0efvUwc4e/0Jez478uW95ibsDdkHAQDF4A3An9plsNyoi9DEq5GeIyAs1R1T84s" +
            "D8jhdKqK2CKRvpZM7EGimANRdmJg12IY/F8bApep1GhIVLUl8RJV/Yku1q0TxMmBrEHCLBwGufnxBK/7KlU9U0TGMwhYFglzddJjDvgScE3iIS" +
            "wSxyCK+HchTA2KwAYNr10EPvPAdvxHLMDXh4TqzzUG3mSvc25wf4uEWzFIuBnxYntci3sxBP4xVRpTE5mK1MKVqL5jQFVReQpVpWRNkosBmZ9C" +
            "VT+znZMD5EXDNR4k4huPAq9X1UvaSGLogcXvmrOPADcnHvp54HwzUelRlVkvpAuAFwP/w76nU9QE3AR8O2jgmfTzzgG3A79J1Wfya1R5+qaak/" +
            "pvT6eqBuzznt+gajDq8vk/B7yjJxnXr3kPVen4B4D/Z5bDd+x6bbdDE25L0RCXKIEzVXWniBxryFicZwHqeEGGVoJEQcb6/evei4eBr1H1Vzxk" +
            "/3/UnsHdVGnL76UqRT/PXmMxkSEpEqQX/rs0onmjqv4SMM4V9w1d9v6kh/jyun4h0VDzY8Bb7QaNOl67epd9oRGETuFaDKgyI7+/Ap//lzoE4Q" +
            "ZmBT2fKhvQxW2qd+4rReTDffpVzNoqO8ZAlmyRfVxEXhUs3oej7tu9ZlFsD85NWr4WtkDPBI6F1ZH2dSdVheQ4sUhzCzUkjlOAg8Dnga+LyNHM" +
            "5z1YE6iqbgO+H3gBcKl9llHGoshZRQvAM4AfFZGP1N2g7mLkg5CSackuReQ+W5jPAW4Iqii7tJwL8E/Mj52252JgpdxzdUl3nyPuCbFD1lOWRV" +
            "UHPV2x2iIamdWAqs7Fu6GIjEXkIHCL7bq5xZNb2HszfTbfB+wKXIthxqwvomxDnV34e+APReR6ETla34/g3oRHYcS0KCJfBH4D+H1b7KdkPkeu" +
            "MnNg1+wVqrrLAuniBNHiFthFSi2weRG5k6rz8aEO5d/hDnseVeXe9KZO9YBq3QDU50gQX2k/KzuQy1RFXw3XNX6frq3zElzjOuZwjf1s1JBteN" +
            "TcKxKBRElUN9af+XSzQkLXYhdVV+Zy5DJIwwKt3dZl4GoRuVZEFoLFr9G9CY8ysmwRkWuBXwXuiogqzmCk0qCLwJOBF+YC6YXHIE5+hhoW4JKq" +
            "DkXkJtup2kxgCWIWO8xNWbdVjB3IRWcgjtOLxHr0sryJqv3+jA7ngLkeRzMByiITR9gRrJf6fZ9gO3equnGYyFjU5LAE/ImI3BIQQy9Nkfr3zW" +
            "27y+JItxlJpEq1i0zTVwn8tFX+PsaKcAui34KtL+BXJuh7OHdGJnhRS+lNcMgGjx2F9Rr11zcB/5eqhXvcQ/PxeLTgi0SmQxLVjwSR/4uiIGec" +
            "GZFMCfVHRORA3WU5JfGO7XUeBN5lQdkdgYWUI8GwPeCpwGUpK8IJYvViHPMzKCBatgdqKTBD+xy6Cao6NXjQ3wT8KVWGqZxQljBV3ZgrbAqv3V" +
            "mBUlkcWxhmKiR3AJ8WkW9Nq9MQWxNmSdwH/B6P7RZtSi+XZgU9L0Xmrmo9galstfZ9d8/vzGAHPkdVLwpy/X3Ljh80fQBZL6KtU1RavtnI4ZxE" +
            "DKDVzQhM8XhXJZEaLIJiLgKLcFtQUh1aDhoRDva79wGfqV2KGT+XYyOJz6rqtcCPU1VODjPp25AkxsDTrU/jePh8OEF0N+3nRGTZct4/GTwEXY" +
            "RZRlQ5+mnnl1xJlZIsJiyJPqqqvyUi/2mDkUSoBqXArwBX2S4+7no9AjWv3VT6D5pxK4pI+6MIq0jNTTk72GQlYc4PI0tlDvi8xbJkhQn0T4Ef" +
            "4UQ6V1pSn8sWTzkf2B8G4Ic+tPek1y600scXPVknX40cdlMV4eztKBNXm58PBhaETmFB7Ap2vklwBvA+Vf2SiHxqlmbuKlgMEpDkVWY5jOJdP8" +
            "iWpIKwpQXjLgkCdEWmL4Mo4HgssNq22TOgLT0d9SLcZvf/6yts3ZZ2T29T1S9S1UkczdRfFJHVtIuqtmJ/aIkVW7xAKnyKRiJS+/jjhO/+XOCv" +
            "qWohxh3Pqd75bgbut4dXZ9hc1vWozeOlQKx2I+lC1M/pvwX+p5HDONFCTZgOjLMjqnoG8I8C2bdBQ+1DGHOYBw4FFtfuIKsxzOg8hEHJeeDbIv" +
            "LoKlpuf9dS9h0eaud4MRu4klJWeKd6vKp+IFFuvMMu3A8E7kLR43wFuLb2EWcwAIYpFJoGM1RqWg2UwS79toAc4nswqGXjzPKL9Rq3A6fawi6C" +
            "ayEdFk9dZ3E/J+uJzkXuTdFAOAVVCnI15RO/YdbDDk5Oe8Yyg6G7cU68cXoM4sSiORt4dYeOxGGPMuOBmaZXrwN5t7WQt5s2GFw/yFcCHwyyFZ" +
            "IRfAlJIA4+xgpTRUPQLg4uHgYeCHb/+WjtFA0NWUOz3B5epWegfv1DwAO2uS1nZO4kIthzg5J6EZENlfLSVVg0o+gYR7L0wx6LrK6N/0hdELPO" +
            "/f31FhSuA3vvAv4oSmXGEflwZx5FbeWjoGVfMinNIpPmrO/5fushKQLSSHX+pginFhA6sorEKtbT8YCRWdGS1q2v52lxOt4tiNm5XKFVUQZSX+" +
            "/2y9q74hJbWL8OfMFM3zJTwJQS6kllJQYZoZjcz+vg4iGqDtFwk6rjDqNM52bYrTkM2rZXW/R3lEhzpq4bQRxi6IVSKx8jqfv3f0dEvmxmm1sP" +
            "/Yhi0QJtp0Yp46bOSxrchramrCKj1fAlERlFqUnNWCCDltdnjeaMFA0DeSRS0SrdglhZN2jZmPha4NfNVC43WOp3vWBXlEqUhI4DEUEUmaYpyZ" +
            "RRDyLLo/6dU4AbROTOaAAOURlz23wLoRKA2WUW5WqQa2kB8dMztR5kNDGW40Y3tyBWhhxuBl4pIsdnOUi1YaR920EUbC02WFl10fC5isQsiaKD" +
            "elVKJLYIFvQ3gS9k0pLLDTtxqklrF1XwdMWDxAGJ7aUSKyobrkX4HA3NnVrySsqVeZBLI4cbgJeKyN0zDkxqlPbTCTUb65JfNuAYRWlQfiJDHE" +
            "3EmZKE20GlGfH3DeS+GBVSFS0uxzaqKsVbVjH+cG5QLyINvShF8OzeV3eI1kVhPllrdgt3QNVV+DwRuXXGcQdNCJIMJzi2UUm6/UUHxab1NFs1" +
            "zjaleidySkpNC3eQcD++KCJ/l7l3GvTVjDIFUqn3BLh0BoVyffAcs4S0xZoiSAPfs5EKpXQNFrkmdquuA2F/Q0SuDGr+xysgqvsXwBeN7csJmr" +
            "Xuoxp5//AG6cWQ4OGVlnkWsSUxSMQmikz7cy12+7cickc4kTtzXg9RqThtjzonUy5Lrdz0RCrx2ztX6trXBGQyeM8PguXSkMEJ4w9fddHa/Hi2" +
            "QR8pusTfP8ukz4+uALnVcYOrReRDs5o6zcbJDklLijL0o+ej2RhN2YzYvbhAVb/dVmNgi+n+oJO0SGQKYtI6DXiuiPxRTv9xFhaXFTm9iEonc6" +
            "FhDkh4zFn84Wvx5uxByhO700PAHwN/FsxQaCtLlqAK7XLg3WY5rJSLtNM0G7fZ10mOjUQORUM5dGzhDalEYG41U3nY0MWYCiqOTQD2SS2j6err" +
            "d3dDgdQgMcTmUeDZqvrklZi2VmfLVHUP1RDpsqH8OzzU4i43AvfGbpATxAmCuE1E/rmI/IwVN9WDU7qSxDLwalX9F0HfxaxjMmoENLaGskkO3Y" +
            "D1JTk3ooiUpx8UkW+IyA1GEvPRc56afRIu4tIW8ZkNJFFfv2/aoh80xDnisXjzVHNSukx/7633aff2V6i6VRej9O0g09Jek+t1tahy+IwUW7Q5" +
            "K5UHHqjqTmPidwKfsRuqHcYBhqIiv6OqT6ilwJx/p4onSUM6MTkYJhC/vcksivmobiEXnKwLhXYCz7VhOE1uxkGq+RU7OhRKDYKejEuA11kQe2" +
            "qFr4Acxqr6GuDl5uYOG+aOhp99G1VJ9kdT98ofYB7TP6EismBm2tEeKcXaTN0H/KHpDrCGOpCbATkJuOxQmFpXUUSWqLRDBy3TwoqobXuZavbJ" +
            "sxoWcP0+N2TciZw7M2dWxw8Dv2AiROUEUv8YEQ4CnYufo1LZWogKwIqWEutTgU+KyO2ptPxWb9bK7RBDEbkReHugJtQ1U7Bso9bfahd7MGNZ/o" +
            "HtlNMexQayIKSFJOJ0aN2wdK+5AjsiwslN1C4CkvghVb04FS8IFtFXgXupshlFy1DdUKdygUrM5R2qemHt+tX3JUcWwWyMmhjGqnqqqr6TquN1" +
            "KcqgaOSWFYkuzgWq2RpsBtn71dqN61LV9wEf6zFMNhxI8lZVfYHV8c+KJI7bw7Q4RQyiPspVsm50imyZtNQzpHzr2Py+kSpCv60hezHIWCs/ai" +
            "P3ytTgIbNSrjM3Rhosk/j158z9eTrwblW9wt5nHAgUSSq4XAsa2fCkF1tg/Wft9eL2dmnI4ihVZuVjwGdzqfnhBrIWVrPIRANr4rXAZ811GCdm" +
            "I6TiEfWieL+qPsuiw7OoqvxBVT1kO+J4is82AL5lwbyVTB2Xdh0OzyAGERNATgkqbnseqerngBclYg+5NGhN8mcCP6Wq/yt+/gLS+BzwLB6ruz" +
            "BosCok2L13A79o7/MJ4B+Au0Xkkfgeq+opVPL+P0I1zvEyO6ejDV2bkiirxkjtYeA9TVkVL7VulxK/Q1XfTCVYMuogVkvgajze5mm+dEqTvo5v" +
            "vNaOWWCsqu+lknGbdb9ISA7/GbjOFut4wkKpskeXZkob4aCq3kSlCraciEvkpmQvU6U+7xSR61IkbwT0Z+b/DxP+f9GiXjWyBX4+8PPAK4EHVf" +
            "UuqsK2ur/nLOBC+709dk2OBxYJmQrJVOxhbLGH/xh0G4+dICaXEv+Qqv4zM+VGGfdME3n5ZeAKVX2jKUkPppjuHcZCZAaFVwOqlNjVInL9DPtG" +
            "6urSOeB3qeZHDkVkNEUlJQ2TuFNdnKmsw1eoKhnPCyzBoqEFWoLp2S9S1QMWyJNgQpfadduvqn8N/AxVx2aX2Zjhe4REMaTqo3hi1GlKIIBzJI" +
            "hr5IKPuc7XsRHMdcBvtXUbewyiWzxCgF+m0hUcNtRGaOL6joF3qurTjKUHU5ragwb9xC5HWNylVMNnZ3VtNRim+1+o1KDOmFJLs2l83CAhMJsl" +
            "e+DTRtpzCVm4IpGNKIL6hZeaiR9npupMx58DXza/PmWRDDM1EmFwdC64N0eBR8wNeMT+v5iYKVpkXK5U/AZOTBP/ZcvWNVqPxRbJp0+rcFSIyP" +
            "3AG4OeDW2oqSBSONoFfFBVT5sidjArXclUJd2siKFuYPqAkcO+Kc+1aOmWlISr0CTDdhC4PghYxorUqcar2hK8EPjpeDxdMHN0ZNmAeyxGpFGA" +
            "MhcwHDYETMPGvLlM1kUa3kOiGbF1D8+rReSmLg2FXgfR3dUYisg1ltkY9miWqgNelwLvWsXswWqPFqzdit8D/oOZsdK0cCcMUkqH6dlNBU5fpp" +
            "ruvSNKAxaZwb21j78IXK6qPxQH9QJX4zvAb9uuvzPhyhSZ8u8iM1m8aOlSLVomlIcZjbpP5fUi8vGmuIMTxORBvQJ4h/mzfUliTFVB97O26ww3" +
            "icxerX04B/wBlY7k3qB0WWcg9T9oUWzqTEJ27a+lyiBsS3R6FpkdvV5oL1fVs2OiD4bW3GHX4DvmbpQt5CORhqUkXJNBQueiyFSbxrGHkbkVQ+" +
            "DnROQq2+zGfQaSOFoe4qBC72HgdYE/qD1cgxL4bVW9wAJNxTqQj1Omn7Q9Z+b1vzdySMnLT1NJmWveyukbtCk+PwT8bRSLGEZfB4mFWlLJuP2r" +
            "ulI2M9nqVrsW+82SoiFOMGjIcuTiMdIw2yL8WWnv/wjwciOHQZ+A8UYRjFmt0XvS0dX4B+DXejR0EaTr9gHvp6q+G2/AWI5GEnvDgBx2N0TRp1" +
            "WRSg19KTLakq3zNqxS9itU6b5cADSOCczbxnAp8FOpUuyAJA5QDfv5qL3H9oRLM8iI7UpLJiSX2pWAGAYWIP4c8BIR+auuboVbEOmF0tUUrjs1" +
            "30slSzbXYxRf7Wq82AKej6xRdkZnYD3UMmX/PbAcBhnh2GmDlJIpk46Vtfp+/r+hmps6H/n+wwYNiqG5Jz+hqk9KxZQCkjgiIu+1gO2DRqBzic" +
            "HAgw6NaCmF7NjaKIPRgCXwHuDHReQrk5DDViAITSwGTZBB556JIGr9KFXR0pHo5rS9V10n8IKgW1RnOIeTDj8jKj6aJHBYxxzebuQgCWtMpnzG" +
            "pEGPskhkY4oJhsv8ZeBWSKZ9WxKzLLcBz8iRYE0cRhQfA94A/AlVv8Ru+/syEuYdZoKORUZij2BI0NDcie3ANUYMbxeR49MonBUbULeBnoNwQu" +
            "1FbShC+qaILNrF1I5Vll8D3hK9T+69wkU6AD5F1WYrUTBv2qCedhz+W/eX3NDRmqh/fpf9+38D/y7hVoSLqraulidUZj5mC6loSUcObGF0tsgC" +
            "V+NmqvqI3Qn3IrROBpH2xDaqdu/G9wisiXtF5D22qfwfqvLz0+wYRs+BZDaaMppdUUvb77Vr/GEqweSXicgX6savaQrghpuwQCqcfnRPsBiars" +
            "GNVKk5ehZQFcB/A55KNddzvuNueD1V/f0zqUqRz16Da3mMSkfzq10eovrnIvINaxK61R7OIojUpyLod4rIch8lq+D3brH32Neyuw+Br1MNrKXH" +
            "gqhTnx8zf/3ShrqEmJT+BvhU12sX6DbsB35TVT9I1fX7bOD7qeTr5oN7VCYqLsOCq5JKBe3L5upeIyI3Rc1k5aZTjzb//im2qPeLyFFVPZdK4/" +
            "+giNxW7zC2C+yj6t9/0NSkBXgyVR76HqoCl53BrMz485c2IOXhcEBKi+xYmFev/32ZMXnZcr1H9n5H7PNeBDwhGko7qdUgHayvulnrHhG5OfwM" +
            "E0icbWt5npYmLLGOrYm9mSa57/YWWBHUtM/ehYHbl9JQqAl+0TIVk0rDnURiltW62IjiYqomsT1U6cm6uGnJLKRDwB0WYL0F+Hp97+xazVQweb" +
            "hCQztSu8HMIuzRa2pm0QtVe/Rn+s6FjL92OY9JOyMtb37HOpiF2efeFkBZl+q2iZokSp77nt+DKz1sxtyBb69GE2CoBGXxrAPmrnwiOKddVMVc" +
            "Q3PTliw9m9tU1V57vF6G1fZ+2IKHTBp2nWEmzamBYEoR7MbDDKmUwA5VXQ5MstwuWyZ2Ys1YHKkmmNSY+SLzOqGvWUTiHmGaqki8hiQsAmmJz0" +
            "hL+7wkXq8tTSlBDwIt56HRM7AEHDAthYk3nhlsRI/522DRdl7oU77nSTt/IDNQWgD1aM4CCcilnPGIhZUhCFWdM9NoW4cKrzjirNH3UxHxkbkK" +
            "Tw6+Nw5ShynSOdt8uz5VgbQstj4umiQ+oyTIKiYBzSxaTbwmPeT521wTbSEWjUguF+jO/Z1S9aUQTMxmJRf/pIt2Day4cRdrfLWHQA9nKLl9YV" +
            "B/n9uhu/jQmvDHJSjdDQOB8w07fZ+cv/b4f5cuztTUqlS6syk92bZAuzzMTb+vLQs59/nKxOtIxhoLP0tpBP89LcFcxyqS4mpZEPO2Myyavzhq" +
            "eYhz9QHx19rHPWjmVhnl8MPXGgUR49sic7/PbtqHCKYhGjagBP20G8myEYRjg2A44xFpyyJy9wqw6ZJFcbv+/uIGWzjSEO+gpaW8yXoqWtyjNt" +
            "m8PtmuXCwjnP24fQPOXnWCmCEGqro3UVVYTJBmLYCHTNJrp1koZWqYDCYnLiKHbMHts4exjNJjmlHZaTsXaYgZNAUEhbyOQ2ohS0tRmLS8V448" +
            "lHY9iabf79vd2UQ+yomCJsdmJ4hgVuGiLcrHZ3LwmuhelMy/67+5haqUeS+VDNcocc51gPJh4JCdz75osrG27Ha0+P2S+XdTMK/o6NNLi0ujDd" +
            "eTRIxBEpV30sMF0kSGo4ubVUbvHb7/KPi7R6laoR1bxYKwXf4OKr2/YRSl15aCnjKhbrQ9+v/YHrJFqvLkMBC4narabhx9v5btWuCxTUapYOh4" +
            "itjENEHQXDxGGwKH2oF8+pZt6xTl77peg2yONSaIoKjoGLB/UrWkoDKx4EQlZXyuh62oJLRgzgw0COLOyYMicthv89q3jkfiKk4eWzQGMXXBiq" +
            "q2mdZxjrg1dtCldBpPd/nncLDRB+fkCGWSirmNlOHwRe9YPwTR96FcgaEr0lRw1dKLkZyQ5Q+2wzEjgpjlAkqQTWrxp2S3UhWGQ1XdHgUj5zJV" +
            "iwDbVHUb3WoAUlmOIjHZKS4j16iXosh0AMbnVnRIY9KS4uyq2iQdS8xzaclU38YxqhhP6ctoCxGEiXGeFcwO0A55fs083Kl22aYahIJ8/cCYKn" +
            "X5pGiEWCr9WA+sCXsxcnUHmqlxyFky2rBg434KmVDsRmbQ/i1TzDWVDhmbM+35ubuP1oNjAxOE7faPo8oKaLR7xurM0pLbb3ID2moNysSCDkeW" +
            "l0GNQ5nZEXNpQg2mSnU5n1TqUFr6K6QhzZiyjCbVfug64YtIiajLuWhDl+x2I989qnqvWxFbx4KY40RPxeGgCKnLw1O25Og16qVo26FKqqIagP" +
            "vtfMqG3XAc9GLc3lDQ1KcAqGvxUmoq+KbdVc3NOztoVXeC2CIE8d2iIRG5k/UTLV+mh67heujFaCKHhC6GNLhZXUq1m8qyu6SEu5SZhyS7oyWY" +
            "7NjkBIGq7uZEV2aXpqG4lLrrw6MNcYeHTM9wF5W4Z66PoQAWROQBO/dzLF5RtsRLpEEHoutilEzQUBraoqXlc7fN4pQOn4sWoRky4jY0iNTE1t" +
            "fxNZzt4VgDgqh983kqncScQpAkgoJxH0UxxZCcULR0mUpx+LxAICYlXHIEeMC0Kc6wXU4a2r5p6a9ock9SMZeypYch1WtChkTKTExFE+rH2iEI" +
            "2uQ+lS2xljITyymB+zz+sIUIwnbrA1SNUbQ0L7VpOTT1GzQ9fEI1iaiIYhYji0kcD2IUS2Yp7I7awWuie9B+v2sfQS4wmYvDlB1EZcqGhqjcNS" +
            "tb+i1mOXUsG4vxzIRjmPCdD6nq4RkoLE/0gJkF8JSE1uTQ3Ijbo98/g5NVj0Pl5sM5oU/HbIRe/Ups3UIpXeOJ0TlNx5BINJhVmEqzDkL1YLxE" +
            "2T+DY1P0YuR8+DALoJZO1C4NYP5AOxxsqtF7fSd8e7rN4dgiBDELURaHw7GJLQiHw+EE4XA4nCAcDocThMPhcIJwOBxOEA6HwwnC4XA4NjlBSD" +
            "Tjci3LxR0OJ4h1VnGpIqIiMp5AA9LhcLBxejGYQOB13oRiCirpPLceHI6tShBB89UjVFoRu+yo3YslKml2b9RyOLaqBSEiC6p6K5UMe9gFenA9" +
            "aFM6HE4Qa08SR6gk5xwOBx6kdDgcThAOh8MJwuFwOEE4HA4nCIfD4QThcDicIBwOhxOEw+FwbBSC8EYrh8MJwuFwOEE4HA4nCFZoSKzfJofDCS" +
            "I1Jau0Vu3Sb5XDgXdzGgZGEvtUdRE41UjCXSKHY4sTREkl9LIHOIsTilFCJQ7jcDjYwulEVR0AZ3NCOk6A4yJy0G+Zw+FwOBxuQfTLXri2pMPh" +
            "cDgcDofDsd7x/wEcH1aVo9a/ZAAAAABJRU5ErkJggg==";
    }
}
