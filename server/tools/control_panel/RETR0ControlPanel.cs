// Project RETR0 - control panel for the RETR0 server package ("RETR0 Server.exe").
//
// A window over the existing scripts. It does not replace them: every action runs retr0_server.cmd / client.cmd
// (the package's own wrappers for retr0_server.ps1 / client.ps1), adb, or an HTTP call to the local sync service, so the Python services and scripts stay plain files that can be edited
// and restarted without rebuilding this program. The exe must sit in the server package folder (next to
// retr0_server.ps1); it finds everything relative to its own location.
//
// Build (Windows' own C# compiler, .NET Framework 4.x, C# 5 syntax only):  tools\control_panel\build.cmd
// Independently written for Project RETR0. Listens on nothing; talks only to 127.0.0.1 and adb.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("RETR0 Server")]
[assembly: System.Reflection.AssemblyProduct("Project RETR0")]
[assembly: System.Reflection.AssemblyVersion("0.3.0.0")]

namespace Retr0
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
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

    sealed class MainForm : Form
    {
        readonly string root;
        readonly TextBox output = new TextBox();
        readonly Label lblDns = new Label(), lblCdn = new Label(), lblSync = new Label(), lblAdb = new Label();
        readonly System.Windows.Forms.Timer statusTimer = new System.Windows.Forms.Timer();
        readonly System.Windows.Forms.Timer logTimer = new System.Windows.Forms.Timer();
        readonly CheckBox chkSync = new CheckBox();
        readonly ComboBox cboProduct = new ComboBox();
        readonly ListView lvGifts = new ListView();
        readonly ListView lvFiles = new ListView();
        readonly ComboBox cboLog = new ComboBox();
        readonly TextBox logView = new TextBox();
        readonly CheckBox chkFollow = new CheckBox();
        volatile bool adbBusy;
        int running;

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
            Font = new Font("Segoe UI", 9.5f);
            Size = new Size(1150, 780);
            MinimumSize = new Size(900, 600);
            StartPosition = FormStartPosition.CenterScreen;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            Controls.Add(BuildBody());
            Controls.Add(BuildHeader());

            statusTimer.Interval = 4000;
            statusTimer.Tick += delegate { RefreshStatus(); };
            statusTimer.Start();
            logTimer.Interval = 2000;
            logTimer.Tick += delegate { if (chkFollow.Checked) LoadLog(); };
            logTimer.Start();
            Shown += delegate { RefreshStatus(); Log("RETR0 Server control panel. Folder: " + root); };
        }

        // ------------------------------------------------------------------ layout
        Control BuildHeader()
        {
            var p = new Panel { Dock = DockStyle.Top, Height = 64, BackColor = Color.FromArgb(18, 22, 34) };
            var title = new Label { Text = "RETR0 SERVER", ForeColor = Color.White, AutoSize = true,
                                    Font = new Font("Segoe UI Semibold", 17f), Location = new Point(14, 13) };
            var sub = new Label { Text = "Project RETR0 · local preservation server control", AutoSize = true,
                                  ForeColor = Color.FromArgb(150, 160, 185), Location = new Point(205, 25) };
            p.Controls.Add(title); p.Controls.Add(sub);
            var flow = new FlowLayoutPanel { Dock = DockStyle.Right, Width = 520, Padding = new Padding(0, 22, 12, 0),
                                             FlowDirection = FlowDirection.LeftToRight, WrapContents = false };
            foreach (var l in new[] { lblDns, lblCdn, lblSync, lblAdb })
            {
                l.AutoSize = true; l.ForeColor = Color.White; l.Margin = new Padding(12, 0, 0, 0);
                l.Font = new Font("Segoe UI", 10f);
                flow.Controls.Add(l);
            }
            p.Controls.Add(flow);
            return p;
        }

        Control BuildBody()
        {
            var split = new SplitContainer { Dock = DockStyle.Fill, Orientation = Orientation.Horizontal,
                                             SplitterDistance = 430, FixedPanel = FixedPanel.None };
            var tabs = new TabControl { Dock = DockStyle.Fill, Padding = new Point(14, 5) };
            tabs.TabPages.Add(ServerTab());
            tabs.TabPages.Add(ClientTab());
            tabs.TabPages.Add(GiftsTab());
            tabs.TabPages.Add(FilesTab());
            tabs.TabPages.Add(LogsTab());
            tabs.SelectedIndexChanged += delegate
            {
                if (tabs.SelectedTab.Text == "Gifts") LoadGifts();
                if (tabs.SelectedTab.Text == "Files") LoadFiles();
                if (tabs.SelectedTab.Text == "Logs") LoadLog();
            };
            split.Panel1.Controls.Add(tabs);

            var bar = new Panel { Dock = DockStyle.Top, Height = 28 };
            bar.Controls.Add(new Label { Text = "Output", AutoSize = true, Location = new Point(6, 6),
                                         Font = new Font("Segoe UI Semibold", 9.5f) });
            var clear = new Button { Text = "Clear", Width = 70, Height = 24, Location = new Point(70, 2) };
            clear.Click += delegate { output.Clear(); };
            bar.Controls.Add(clear);
            output.Multiline = true; output.ReadOnly = true; output.ScrollBars = ScrollBars.Both; output.WordWrap = false;
            output.Dock = DockStyle.Fill; output.Font = new Font("Consolas", 9.5f);
            output.BackColor = Color.FromArgb(14, 16, 22); output.ForeColor = Color.FromArgb(205, 214, 230);
            split.Panel2.Controls.Add(output);
            split.Panel2.Controls.Add(bar);
            return split;
        }

        static FlowLayoutPanel Row(Control parent, string heading, string help)
        {
            var box = new GroupBox { Text = heading, Dock = DockStyle.Top, Height = 104, Padding = new Padding(10, 6, 10, 6) };
            var flow = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 40, WrapContents = false };
            var tip = new Label { Text = help, Dock = DockStyle.Top, Height = 34, ForeColor = Color.DimGray };
            box.Controls.Add(tip); box.Controls.Add(flow);
            parent.Controls.Add(box);
            parent.Controls.SetChildIndex(box, 0);
            return flow;
        }

        static Button Btn(FlowLayoutPanel f, string text, EventHandler click, int width = 150)
        {
            var b = new Button { Text = text, Width = width, Height = 32, Margin = new Padding(0, 0, 8, 0) };
            b.Click += click;
            f.Controls.Add(b);
            return b;
        }

        TabPage ServerTab()
        {
            var t = new TabPage("Server") { Padding = new Padding(10), AutoScroll = true };
            var r = Row(t, "Services (dns · cdn · sync)",
                "Starts the three Python services in services\\ (127.0.0.1 only). Sync = the CloudCell replacement " +
                "(gifts, cloud saves, racing codes). Edit a .py file, then Restart: no rebuild needed.");
            chkSync.Text = "With sync"; chkSync.Checked = true; chkSync.AutoSize = true;
            chkSync.Margin = new Padding(0, 7, 12, 0);
            r.Controls.Add(chkSync);
            Btn(r, "Start", delegate { RunScript("retr0_server.cmd", "start" + SyncArg(), "Start server"); }, 110);
            Btn(r, "Stop", delegate { RunScript("retr0_server.cmd", "stop", "Stop server"); }, 110);
            Btn(r, "Restart", delegate { RunScript("retr0_server.cmd", "restart" + SyncArg(), "Restart server"); }, 110);
            Btn(r, "Status", delegate { RunScript("retr0_server.cmd", "status", "Server status"); }, 110);

            var r2 = Row(t, "Help", "The full guide is OVERVIEW.md in the server folder; README.md has the short version.");
            Btn(r2, "Open OVERVIEW.md", delegate { OpenForEdit(Path.Combine(root, "OVERVIEW.md")); }, 170);
            Btn(r2, "Open README.md", delegate { OpenForEdit(Path.Combine(root, "README.md")); }, 170);
            Btn(r2, "Open server folder", delegate { Explore(root); }, 170);
            return t;
        }

        string SyncArg() { return chkSync.Checked ? " -WithSync" : ""; }

        TabPage ClientTab()
        {
            var t = new TabPage("Emulator & client") { Padding = new Padding(10), AutoScroll = true };
            var r1 = Row(t, "Play", "Play = check the emulator runs the RETR0 client, set adb reverse 8780, start the game. " +
                                    "Start the server first (Server tab, With sync).");
            Btn(r1, "Play", delegate { RunScript("client.cmd", "play", "Play"); }, 110);
            Btn(r1, "Client status", delegate { RunScript("client.cmd", "status", "Client status"); });
            Btn(r1, "adb devices", delegate { RunExe("adb", "devices -l", "adb devices"); });

            var r2 = Row(t, "Install (keeps your progress)",
                "Apply = swap in the RETR0 client in place. Restore = put the original 14.0.1 APK back. After an " +
                "emulator restart the swapped APK is gone (data is kept): use Fix after emulator restart.");
            Btn(r2, "Apply client", delegate { RunScript("client.cmd", "apply", "Apply client"); });
            Btn(r2, "Restore original", delegate { RunScript("client.cmd", "restore", "Restore original"); });
            Btn(r2, "Fix after emulator restart", delegate { RunScript("client.cmd", "fix-reboot", "Fix after emulator restart"); }, 210);
            Btn(r2, "New install (deletes data)...", delegate
            {
                if (MessageBox.Show(this, "New install UNINSTALLS the game and deletes its data and downloaded assets.\n\n" +
                    "A console window opens and asks you to type YES. Continue?", "RETR0 Server",
                    MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes)
                    OpenConsole("client.cmd", "install-fresh");
            }, 210);

            var r3 = Row(t, "Username button text",
                "Renames Settings > ENTER RACING CODE to \"Change Username (Restart Required)\" (edits two of the " +
                "game's UI files on the emulator; originals kept in backups\\ui_text).");
            Btn(r3, "Apply button text", delegate { RunScript("client.cmd", "ui-text", "Apply button text"); }, 170);
            Btn(r3, "Restore button text", delegate { RunScript("client.cmd", "ui-text-restore", "Restore button text"); }, 170);
            return t;
        }

        TabPage GiftsTab()
        {
            var t = new TabPage("Gifts") { Padding = new Padding(10) };
            var top = new GroupBox { Text = "Send a gift (store catalogue amounts only)", Dock = DockStyle.Top,
                                     Height = 112, Padding = new Padding(10, 6, 10, 6) };
            var flow = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 40, WrapContents = false };
            cboProduct.DropDownStyle = ComboBoxStyle.DropDownList; cboProduct.Width = 520;
            foreach (var p in Products) cboProduct.Items.Add(p);
            cboProduct.SelectedIndex = 0;
            flow.Controls.Add(cboProduct);
            Btn(flow, "Send gift", delegate { SendGift(); }, 120);
            Btn(flow, "Refresh list", delegate { LoadGifts(); }, 120);
            var tip = new Label { Dock = DockStyle.Top, Height = 38, ForeColor = Color.DimGray,
                Text = "The game picks gifts up when it starts. Gold appears in Notifications (tap to claim); R$ and " +
                       "M$ are credited at once with a RETR0 popup. Gifts currently go to every connected game." };
            top.Controls.Add(tip); top.Controls.Add(flow);

            // Custom gift: any amount within the server's limits and/or cars by id, one instant community gift.
            var custom = new GroupBox { Text = "Custom gift (any amount, or cars by id)", Dock = DockStyle.Top,
                                        Height = 116, Padding = new Padding(10, 6, 10, 6) };
            var cflow = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 40, WrapContents = false };
            AddField(cflow, "Gold", numGold, 1000000);
            AddField(cflow, "R$", numMoney, 100000000);
            AddField(cflow, "M$", numMDollars, 100000000);
            cflow.Controls.Add(new Label { Text = "Car ids", AutoSize = true, Margin = new Padding(6, 8, 4, 0) });
            txtCars.Width = 90; txtCars.Margin = new Padding(0, 4, 10, 0);
            cflow.Controls.Add(txtCars);
            cflow.Controls.Add(new Label { Text = "Message", AutoSize = true, Margin = new Padding(6, 8, 4, 0) });
            txtMessage.Width = 150; txtMessage.Margin = new Padding(0, 4, 10, 0);
            cflow.Controls.Add(txtMessage);
            Btn(cflow, "Send custom gift", delegate { SendCustomGift(); }, 140);
            var ctip = new Label { Dock = DockStyle.Top, Height = 38, ForeColor = Color.DimGray,
                Text = "Credited at once with a RETR0 popup the next time the game starts. Car ids are the game's car " +
                       "numbers (e.g. 383 = Audi e-tron FE06), several separated by commas. Leave a box at 0 to skip it." };
            custom.Controls.Add(ctip); custom.Controls.Add(cflow);

            lvGifts.Dock = DockStyle.Fill; lvGifts.View = View.Details; lvGifts.FullRowSelect = true;
            lvGifts.GridLines = true;
            foreach (var c in new[] { "Gift", "Status", "Product", "Reward", "Queued", "Delivered", "Source / note" })
                lvGifts.Columns.Add(c, c == "Reward" || c == "Source / note" ? 300 : 110);
            t.Controls.Add(lvGifts);
            t.Controls.Add(custom);
            t.Controls.Add(top);
            return t;
        }

        readonly NumericUpDown numGold = new NumericUpDown(), numMoney = new NumericUpDown(), numMDollars = new NumericUpDown();
        readonly TextBox txtCars = new TextBox(), txtMessage = new TextBox();

        static void AddField(FlowLayoutPanel f, string label, NumericUpDown n, int max)
        {
            f.Controls.Add(new Label { Text = label, AutoSize = true, Margin = new Padding(6, 8, 4, 0) });
            n.Maximum = max; n.Minimum = 0; n.ThousandsSeparator = true; n.Width = 108;
            n.Increment = max >= 100000000 ? 10000 : 10; n.Margin = new Padding(0, 4, 8, 0);
            f.Controls.Add(n);
        }

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
            }
            catch (WebException e)
            {
                string body = "";
                if (e.Response != null) using (var sr = new StreamReader(e.Response.GetResponseStream())) body = sr.ReadToEnd();
                Log("! refused: " + e.Message + (body.Length > 0 ? " - " + body : "") +
                    (e.Response == null ? "  (is the server running with sync?)" : ""));
            }
            LoadGifts();
        }

        TabPage FilesTab()
        {
            var t = new TabPage("Files") { Padding = new Padding(10) };
            var top = new GroupBox { Text = "Server files (double-click a file to edit it; restart the server afterwards)",
                                     Dock = DockStyle.Top, Height = 64, Padding = new Padding(10, 6, 10, 6) };
            var flow = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
            foreach (var d in new[] { "services", "tools", "config", "runtime", "backups", @"client\apk" })
            {
                string dir = d;
                Btn(flow, dir + "\\", delegate { Explore(Path.Combine(root, dir)); }, 110);
            }
            top.Controls.Add(flow);
            lvFiles.Dock = DockStyle.Fill; lvFiles.View = View.Details; lvFiles.FullRowSelect = true;
            lvFiles.Columns.Add("File", 430); lvFiles.Columns.Add("Size", 90); lvFiles.Columns.Add("Modified", 160);
            lvFiles.Columns.Add("What", 360);
            lvFiles.DoubleClick += delegate
            {
                if (lvFiles.SelectedItems.Count > 0) OpenForEdit(Path.Combine(root, lvFiles.SelectedItems[0].Text));
            };
            var menu = new ContextMenuStrip();
            menu.Items.Add("Edit", null, delegate { if (lvFiles.SelectedItems.Count > 0) OpenForEdit(Path.Combine(root, lvFiles.SelectedItems[0].Text)); });
            menu.Items.Add("Show in folder", null, delegate { if (lvFiles.SelectedItems.Count > 0) ShowInFolder(Path.Combine(root, lvFiles.SelectedItems[0].Text)); });
            lvFiles.ContextMenuStrip = menu;
            t.Controls.Add(lvFiles);
            t.Controls.Add(top);
            return t;
        }

        TabPage LogsTab()
        {
            var t = new TabPage("Logs") { Padding = new Padding(10) };
            var flow = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 38, WrapContents = false };
            cboLog.DropDownStyle = ComboBoxStyle.DropDownList; cboLog.Width = 300;
            foreach (var f in new[] { "sync.log", "cdn.out.log", "cdn.err.log", "sync.err.log", "dns.out.log", "dns.err.log" })
                cboLog.Items.Add(f);
            cboLog.SelectedIndex = 0;
            cboLog.SelectedIndexChanged += delegate { LoadLog(); };
            flow.Controls.Add(cboLog);
            chkFollow.Text = "Follow (refresh every 2 s)"; chkFollow.AutoSize = true; chkFollow.Checked = true;
            chkFollow.Margin = new Padding(10, 6, 10, 0);
            flow.Controls.Add(chkFollow);
            Btn(flow, "Open in editor", delegate { OpenForEdit(Path.Combine(root, "runtime", cboLog.Text)); }, 130);
            logView.Multiline = true; logView.ReadOnly = true; logView.ScrollBars = ScrollBars.Both; logView.WordWrap = false;
            logView.Dock = DockStyle.Fill; logView.Font = new Font("Consolas", 9f);
            t.Controls.Add(logView);
            t.Controls.Add(flow);
            return t;
        }

        // ------------------------------------------------------------------ status
        void RefreshStatus()
        {
            var tcp = new HashSet<int>(IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners()
                                       .Where(e => IPAddress.IsLoopback(e.Address) || e.Address.Equals(IPAddress.Any)).Select(e => e.Port));
            var udp = new HashSet<int>(IPGlobalProperties.GetIPGlobalProperties().GetActiveUdpListeners()
                                       .Where(e => IPAddress.IsLoopback(e.Address) || e.Address.Equals(IPAddress.Any)).Select(e => e.Port));
            SetLight(lblDns, "DNS", PidAlive("dns") && udp.Contains(53));
            SetLight(lblCdn, "CDN :8780", PidAlive("cdn") && tcp.Contains(8780));
            SetLight(lblSync, "Sync :8781", PidAlive("sync") && tcp.Contains(8781));
            if (!adbBusy)
            {
                adbBusy = true;
                ThreadPool.QueueUserWorkItem(delegate
                {
                    string state = RunCapture("adb", "get-state", 3000);
                    bool ok = state != null && state.Trim() == "device";
                    try { BeginInvoke((Action)delegate { SetLight(lblAdb, "Emulator", ok); }); } catch { }
                    adbBusy = false;
                });
            }
        }

        bool PidAlive(string name)
        {
            try
            {
                int pid = int.Parse(File.ReadAllText(Path.Combine(root, "runtime", name + ".pid")).Trim());
                return !Process.GetProcessById(pid).HasExited;
            }
            catch { return false; }
        }

        static void SetLight(Label l, string name, bool on)
        {
            l.Text = "● " + name;
            l.ForeColor = on ? Color.FromArgb(61, 220, 151) : Color.FromArgb(240, 90, 90);
        }

        // ------------------------------------------------------------------ running things
        void Log(string line)
        {
            if (InvokeRequired) { try { BeginInvoke((Action<string>)Log, line); } catch { } return; }
            output.AppendText(line + Environment.NewLine);
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
            var psi = new ProcessStartInfo(exe, args)
            {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            try
            {
                var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
                p.OutputDataReceived += (s, e) => { if (e.Data != null) Log(e.Data); };
                p.ErrorDataReceived += (s, e) => { if (e.Data != null && e.Data.Trim().Length > 0) Log("! " + e.Data); };
                // The server services inherit the output pipe and keep it open after the script ends, so "done" is
                // reported when the script process exits, not when its output closes.
                p.Exited += delegate
                {
                    int code = -1; try { code = p.ExitCode; } catch { }
                    Interlocked.Decrement(ref running);
                    Log("< " + title + " finished (exit " + code + ")");
                    try { BeginInvoke((Action)RefreshStatus); } catch { }
                };
                p.Start();
                Interlocked.Increment(ref running);
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
            }
            catch (Exception e) { Log("! could not start " + exe + ": " + e.Message); }
        }

        // Interactive commands (install-fresh asks for YES) run in their own console window.
        void OpenConsole(string script, string args)
        {
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
        void SendGift()
        {
            var p = (Product)cboProduct.SelectedItem;
            if (MessageBox.Show(this, string.Format("Send {0:N0} {1} (product {2})?\n\nThe game receives it the next time it " +
                "starts. Gold: claim it from Notifications. R$/M$: credited at once with a popup.", p.Amount, p.Currency, p.Id),
                "Send gift", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            PostGift("product=" + p.Id, string.Format("{0:N0} {1} (product {2})", p.Amount, p.Currency, p.Id));
        }

        void LoadGifts()
        {
            lvGifts.Items.Clear();
            string path = Path.Combine(root, @"runtime\sync_data\state.json");
            try
            {
                string json;
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var sr = new StreamReader(fs)) json = sr.ReadToEnd();
                var state = (Dictionary<string, object>)new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.DeserializeObject(json);
                object giftsObj;
                if (!state.TryGetValue("gifts", out giftsObj)) return;
                var gifts = (Dictionary<string, object>)giftsObj;
                var rows = new List<KeyValuePair<string, Dictionary<string, object>>>();
                foreach (var status in new[] { "pending", "claimed", "held" })
                {
                    object list;
                    if (gifts.TryGetValue(status, out list) && list is IEnumerable)
                        foreach (var g in (IEnumerable)list)
                            rows.Add(new KeyValuePair<string, Dictionary<string, object>>(status, (Dictionary<string, object>)g));
                }
                foreach (var kv in rows.OrderByDescending(x => Convert.ToInt64(Get(x.Value, "id", 0))))
                {
                    var g = kv.Value;
                    string status = kv.Key == "claimed" ? "delivered" : kv.Key;
                    var it = new ListViewItem(Convert.ToString(Get(g, "id", "")));
                    it.SubItems.Add(status);
                    it.SubItems.Add(Convert.ToString(Get(g, "product_id", "")));
                    string msg = Convert.ToString(Get(g, "message", ""));
                    it.SubItems.Add(msg.Length > 0 ? msg.Replace("Preservation grant: ", "")
                        : Convert.ToString(Get(g, "metadata", "")).Split(new[] { ", displayImage" }, StringSplitOptions.None)[0]);
                    it.SubItems.Add(When(Get(g, "queued", null)));
                    it.SubItems.Add(When(Get(g, "claimed", null)));
                    string note = Convert.ToString(Get(g, "note", ""));
                    it.SubItems.Add(Convert.ToString(Get(g, "source", "")) + (note.Length > 0 ? " - " + note : ""));
                    if (status == "pending") it.ForeColor = Color.DarkOrange;
                    else if (status == "held") it.ForeColor = Color.Gray;
                    lvGifts.Items.Add(it);
                }
            }
            catch (FileNotFoundException) { }
            catch (DirectoryNotFoundException) { }
            catch (Exception e) { Log("! could not read gifts: " + e.Message); }
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
            lvFiles.Items.Clear();
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
                var it = new ListViewItem(rel);
                it.SubItems.Add((fi.Length / 1024.0).ToString("0.0") + " KB");
                it.SubItems.Add(fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm"));
                string what; it.SubItems.Add(About.TryGetValue(rel, out what) ? what : "");
                lvFiles.Items.Add(it);
            }
        }

        void LoadLog()
        {
            string path = Path.Combine(root, "runtime", cboLog.Text);
            string text;
            try
            {
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    long start = Math.Max(0, fs.Length - 96 * 1024);
                    fs.Seek(start, SeekOrigin.Begin);
                    using (var sr = new StreamReader(fs, Encoding.UTF8)) text = sr.ReadToEnd();
                    if (start > 0) { int nl = text.IndexOf('\n'); if (nl >= 0) text = text.Substring(nl + 1); }
                }
            }
            catch (FileNotFoundException) { text = "(no " + cboLog.Text + " yet)"; }
            catch (Exception e) { text = "could not read: " + e.Message; }
            text = text.Replace("\r\n", "\n").Replace("\n", "\r\n");
            if (logView.Text == text) return;
            logView.Text = text;
            logView.SelectionStart = logView.TextLength;
            logView.ScrollToCaret();
        }
    }
}
