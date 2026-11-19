// Countertop menu bar app
// Shows whether the dashboard server is running and whether the Echo is showing the page,
// and lets you start / stop / restart the server. Build with ./build.sh
import AppKit

let PORT = 8090

final class Status {
    var serverPIDs: [Int32] = []
    var serverNew = false            // true when /version answers (new server code is running)
    var beatAge: TimeInterval? = nil // seconds since the Echo's last heartbeat
    var beatFS = false
    var beatAudio: Bool? = nil
    var beatUp = 0
    var beatShell = false
    var fxText = ""
    var recentErrors: [String] = []
    var listText = ""
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let menu = NSMenu()
    var status = Status()
    var timer: Timer?
    var busy: String? = nil          // "Restarting…" etc.
    let defaults = UserDefaults.standard

    var projectDir: URL {
        if let p = defaults.string(forKey: "projectDir"), !p.isEmpty { return URL(fileURLWithPath: p) }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Projects/hoya")
    }
    /// Heartbeats and page errors the dashboard reports (the server renamed this from silk_collect.log on first start).
    var logURL: URL {
        let new = projectDir.appendingPathComponent("work/heartbeat.log")
        let old = projectDir.appendingPathComponent("work/silk_collect.log")
        return FileManager.default.fileExists(atPath: new.path) || !FileManager.default.fileExists(atPath: old.path) ? new : old
    }
    var serverLogURL: URL { projectDir.appendingPathComponent("work/server.log") }
    var keepRunning: Bool {
        get { defaults.bool(forKey: "keepRunning") }
        set { defaults.set(newValue, forKey: "keepRunning") }
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        menu.delegate = self
        item.menu = menu
        setIcon(.systemGray)
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in self?.refresh() }
    }

    // MARK: - status

    func refresh() {
        DispatchQueue.global().async {
            let s = Status()
            s.serverPIDs = self.listeningPIDs()
            self.readLog(into: s)
            let group = DispatchGroup()
            if !s.serverPIDs.isEmpty {
                group.enter()
                self.fetchJSON("/version") { j in s.serverNew = (j?["v"] != nil); group.leave() }
                group.enter()
                self.fetchJSON("/notes") { j in
                    if let j = j {
                        let items = (j["items"] as? [[String: Any]]) ?? []
                        let open = items.filter { !(($0["done"] as? Bool) ?? false) }.count
                        if let e = j["error"] as? String, !e.isEmpty {
                            s.listText = "Grocery list: Reminders error – " + String(e.prefix(60))
                        } else if let l = j["list"] as? String {
                            s.listText = "Grocery list: \(open) item\(open == 1 ? "" : "s") from Reminders “\(l)”"
                        } else {
                            s.listText = "Grocery list: \(open) item\(open == 1 ? "" : "s")"
                        }
                    }
                    group.leave()
                }
            }
            _ = group.wait(timeout: .now() + 5)
            DispatchQueue.main.async {
                self.status = s
                self.updateIcon()
                if self.keepRunning && s.serverPIDs.isEmpty && self.busy == nil {
                    self.startServer()
                }
            }
        }
    }

    func updateIcon() {
        let s = status
        if busy != nil { setIcon(.systemBlue); return }
        if s.serverPIDs.isEmpty { setIcon(.systemRed); return }
        let stale = (s.beatAge ?? 99999) > 180
        if stale || !s.recentErrors.isEmpty { setIcon(.systemOrange); return }
        setIcon(.systemGreen)
    }

    func setIcon(_ color: NSColor) {
        guard let button = item.button else { return }
        let cfg = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
            .applying(NSImage.SymbolConfiguration(paletteColors: [color]))
        if let img = NSImage(systemSymbolName: "fork.knife.circle.fill", accessibilityDescription: "Countertop")?
            .withSymbolConfiguration(cfg) {
            img.isTemplate = false
            button.image = img
            button.title = ""
        } else {
            button.title = "🍳"
        }
        button.toolTip = "Countertop"
    }

    func run(_ path: String, _ args: [String]) -> String {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = Pipe()
        do { try p.run() } catch { return "" }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        return String(data: data, encoding: .utf8) ?? ""
    }

    func listeningPIDs() -> [Int32] {
        run("/usr/sbin/lsof", ["-nP", "-iTCP:\(PORT)", "-sTCP:LISTEN", "-t"])
            .split(separator: "\n").compactMap { Int32($0.trimmingCharacters(in: .whitespaces)) }
    }

    func fetchJSON(_ path: String, _ done: @escaping ([String: Any]?) -> Void) {
        guard let url = URL(string: "http://127.0.0.1:\(PORT)\(path)") else { done(nil); return }
        var req = URLRequest(url: url)
        req.timeoutInterval = 4
        URLSession.shared.dataTask(with: req) { data, resp, _ in
            guard let data = data, let http = resp as? HTTPURLResponse, http.statusCode == 200,
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { done(nil); return }
            done(obj)
        }.resume()
    }

    /// Reads the end of work/heartbeat.log for the Echo's last heartbeat and recent JS errors.
    func readLog(into s: Status) {
        guard let fh = try? FileHandle(forReadingFrom: logURL) else { return }
        defer { try? fh.close() }
        let size = (try? fh.seekToEnd()) ?? 0
        let chunk: UInt64 = 200_000
        try? fh.seek(toOffset: size > chunk ? size - chunk : 0)
        guard let data = try? fh.readToEnd(), let text = String(data: data, encoding: .utf8) else { return }
        let lines = text.split(separator: "\n").suffix(1500)
        let mtime = ((try? FileManager.default.attributesOfItem(atPath: logURL.path))?[.modificationDate] as? Date) ?? Date()
        var foundBeat = false
        var pastReload = false
        var errs: [String] = []
        for line in lines.reversed() {
            guard let d = line.data(using: .utf8),
                  let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { continue }
            let task = j["task"] as? String ?? ""
            let client = j["client"] as? String ?? ""
            let t = j["t"] as? String ?? ""
            let age = ageOf(t, logMtime: mtime)
            if task == "beat" && client != "127.0.0.1" && !foundBeat {
                foundBeat = true
                s.beatAge = age
                let r = j["result"] as? [String: Any] ?? [:]
                s.beatFS = (r["fs"] as? Bool) ?? false
                s.beatAudio = r["audio"] as? Bool
                s.beatUp = (r["up"] as? Int) ?? 0
                s.beatShell = (r["shell"] as? Bool) ?? false
                if let fx = r["fx"] as? [String: Any] {
                    var parts: [String] = []
                    if let sky = fx["sky"] as? String { parts.append("sky \(sky)") }
                    if let w = fx["fx"] as? String { parts.append(w) }
                    if let f = fx["fun"] as? String { parts.append(f) }
                    if let fps = (fx["funFps"] ?? fx["fps"]) as? Int { parts.append("\(fps) fps") }
                    s.fxText = parts.joined(separator: " · ")
                }
            }
            // only errors from the page that's on screen now: stop at the last reload of the dashboard
            if task == "frame-refresh" { pastReload = true }
            if task == "js-error", !pastReload, let a = age, a < 1800 {
                let msg = (j["error"] as? String) ?? "error"
                if !msg.hasPrefix("reminders:") { errs.append(msg) }
            }
            if let a = age, a > 3600, foundBeat { break }
        }
        s.recentErrors = errs
    }

    /// Log lines only carry "HH:MM:SS"; assume today, or yesterday if that would be in the future.
    func ageOf(_ t: String, logMtime: Date) -> TimeInterval? {
        let p = t.split(separator: ":").compactMap { Int($0) }
        guard p.count == 3 else { return nil }
        let cal = Calendar.current
        guard var d = cal.date(bySettingHour: p[0], minute: p[1], second: p[2], of: Date()) else { return nil }
        if d > Date().addingTimeInterval(60) { d = d.addingTimeInterval(-86400) }
        return Date().timeIntervalSince(d)
    }

    // MARK: - server control

    func shellQuote(_ s: String) -> String { "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'" }

    func startServer() {
        let dir = shellQuote(projectDir.path)
        // -i so ~/.zshrc runs and the same python3 you use in Terminal (with dateutil) is found
        let cmd = "cd \(dir) && nohup python3 tools/countertop.py --port \(PORT) --also-tls --tls-port 8443 > work/server.log 2>&1 &"
        _ = run("/bin/zsh", ["-lic", cmd])
    }

    func stopServer() {
        for pid in listeningPIDs() { kill(pid, SIGTERM) }
        for _ in 0..<20 {
            if listeningPIDs().isEmpty { return }
            Thread.sleep(forTimeInterval: 0.25)
        }
        for pid in listeningPIDs() { kill(pid, SIGKILL) }
        Thread.sleep(forTimeInterval: 0.5)
    }

    func doBusy(_ label: String, _ work: @escaping () -> Void) {
        busy = label
        updateIcon()
        DispatchQueue.global().async {
            work()
            Thread.sleep(forTimeInterval: 2.5)
            DispatchQueue.main.async {
                self.busy = nil
                self.refresh()
            }
        }
    }

    @objc func restart() { doBusy("Restarting…") { self.stopServer(); self.startServer() } }
    @objc func start() { doBusy("Starting…") { self.startServer() } }
    @objc func stop() {
        keepRunning = false
        doBusy("Stopping…") { self.stopServer() }
    }
    @objc func refreshEcho() {
        // the /dash shell reloads its frame when /version changes, which follows dash3.html's modification time
        let f = projectDir.appendingPathComponent("tools/dash3.html")
        try? FileManager.default.setAttributes([.modificationDate: Date()], ofItemAtPath: f.path)
    }
    @objc func openURL(_ sender: NSMenuItem) {
        if let s = sender.representedObject as? String, let u = URL(string: s) { NSWorkspace.shared.open(u) }
    }
    @objc func openLog() { NSWorkspace.shared.open(logURL) }
    @objc func openServerLog() { NSWorkspace.shared.open(serverLogURL) }
    @objc func openFolder() { NSWorkspace.shared.activateFileViewerSelecting([projectDir.appendingPathComponent("tools/countertop.py")]) }
    @objc func toggleKeep() { keepRunning.toggle(); refresh() }
    @objc func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.directoryURL = projectDir
        panel.message = "Choose the hoya project folder (the one containing tools/ and work/)"
        NSApp.activate(ignoringOtherApps: true)
        if panel.runModal() == .OK, let u = panel.url { defaults.set(u.path, forKey: "projectDir"); refresh() }
    }

    var agentURL: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/LaunchAgents/local.kitchen-dashboard.menubar.plist")
    }
    @objc func toggleLogin() {
        if FileManager.default.fileExists(atPath: agentURL.path) {
            try? FileManager.default.removeItem(at: agentURL)
        } else {
            let exe = Bundle.main.executablePath ?? CommandLine.arguments[0]
            let plist: [String: Any] = ["Label": "local.kitchen-dashboard.menubar",
                                        "ProgramArguments": [exe], "RunAtLoad": true]
            try? FileManager.default.createDirectory(at: agentURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            if let data = try? PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0) {
                try? data.write(to: agentURL)
            }
        }
    }

    // MARK: - menu

    /// Status lines are drawn as plain labels (not disabled menu items, which macOS greys out).
    /// The color only goes on the leading "●"; the text stays at full contrast.
    func info(_ text: String, color: NSColor? = nil, bold: Bool = false) -> NSMenuItem {
        let mi = NSMenuItem(title: text, action: nil, keyEquivalent: "")
        let font = NSFont.menuFont(ofSize: 0)
        let dot = text.hasPrefix("●")
        let base: NSColor = (color != nil && !dot) ? color! : (text.hasPrefix("   ") ? .secondaryLabelColor : .labelColor)
        let s = NSMutableAttributedString(string: text, attributes: [.font: bold ? NSFont.boldSystemFont(ofSize: 13) : font, .foregroundColor: base])
        if dot, let c = color {
            s.addAttribute(.foregroundColor, value: c, range: NSRange(location: 0, length: 1))
        }
        let label = NSTextField(labelWithAttributedString: s)
        label.lineBreakMode = .byTruncatingTail
        label.sizeToFit()
        let w = max(label.frame.width + 28, 300)
        let box = NSView(frame: NSRect(x: 0, y: 0, width: w, height: 22))
        label.frame = NSRect(x: 14, y: (22 - label.frame.height) / 2, width: label.frame.width + 4, height: label.frame.height)
        box.addSubview(label)
        mi.view = box
        return mi
    }
    func action(_ title: String, _ sel: Selector, key: String = "", url: String? = nil) -> NSMenuItem {
        let mi = NSMenuItem(title: title, action: sel, keyEquivalent: key)
        mi.target = self
        mi.representedObject = url
        return mi
    }
    func dur(_ secs: Int) -> String {
        if secs < 90 { return "\(secs)s" }
        if secs < 5400 { return "\(secs / 60) min" }
        return "\(secs / 3600)h \((secs % 3600) / 60)m"
    }

    func menuNeedsUpdate(_ m: NSMenu) {
        m.removeAllItems()
        let s = status
        m.addItem(info("Countertop", bold: true))

        if let b = busy {
            m.addItem(info(b, color: .systemBlue))
        } else if s.serverPIDs.isEmpty {
            m.addItem(info("● Server stopped", color: .systemRed))
        } else {
            let pid = s.serverPIDs.map(String.init).joined(separator: ", ")
            m.addItem(info("● Server running · pid \(pid)", color: .systemGreen))
            if !s.serverNew { m.addItem(info("   Old server code. Restart to update", color: .systemOrange)) }
        }

        if let a = s.beatAge {
            if a < 180 {
                m.addItem(info("● Echo showing the dashboard · seen \(dur(Int(a))) ago", color: .systemGreen))
            } else {
                m.addItem(info("● Echo not seen for \(dur(Int(a)))", color: .systemOrange))
            }
            var bits = ["Fullscreen " + (s.beatFS ? "on" : "off")]
            if let au = s.beatAudio { bits.append("keep-alive " + (au ? "on" : "off")) }
            bits.append("page up \(dur(s.beatUp))")
            m.addItem(info("   " + bits.joined(separator: " · ")))
            if !s.fxText.isEmpty { m.addItem(info("   Effects: " + s.fxText)) }
        } else {
            m.addItem(info("● No heartbeat from the Echo yet", color: .systemOrange))
        }
        if s.recentErrors.isEmpty {
            m.addItem(info("   No page errors in the last 30 min"))
        } else {
            let e = s.recentErrors[0]
            let mi = action("⚠︎ \(s.recentErrors.count) page error\(s.recentErrors.count == 1 ? "" : "s"): \(String(e.prefix(60)))", #selector(openLog))
            m.addItem(mi)
        }
        if !s.listText.isEmpty { m.addItem(info("   " + s.listText)) }

        m.addItem(.separator())
        if s.serverPIDs.isEmpty {
            m.addItem(action("Start Server", #selector(start), key: "s"))
        } else {
            m.addItem(action("Restart Server", #selector(restart), key: "r"))
            m.addItem(action("Stop Server", #selector(stop)))
        }
        let re = action("Reload Dashboard on Echo", #selector(refreshEcho), key: "e")
        re.isEnabled = s.serverNew && s.beatShell
        if !re.isEnabled { re.toolTip = "Works once the Echo is showing /dash from the restarted server" }
        m.addItem(re)

        m.addItem(.separator())
        m.addItem(action("Dashboard Controls…", #selector(openURL(_:)), url: "http://127.0.0.1:\(PORT)/control"))
        m.addItem(action("Open Dashboard", #selector(openURL(_:)), url: "http://127.0.0.1:\(PORT)/dash"))
        m.addItem(action("Open Grocery List Page", #selector(openURL(_:)), url: "http://127.0.0.1:\(PORT)/list"))
        m.addItem(action("Show Heartbeat Log", #selector(openLog)))
        m.addItem(action("Show Server Output", #selector(openServerLog)))
        m.addItem(action("Show Project in Finder", #selector(openFolder)))

        m.addItem(.separator())
        let keep = action("Keep Server Running", #selector(toggleKeep))
        keep.state = keepRunning ? .on : .off
        m.addItem(keep)
        let login = action("Open at Login", #selector(toggleLogin))
        login.state = FileManager.default.fileExists(atPath: agentURL.path) ? .on : .off
        m.addItem(login)
        m.addItem(action("Project Folder… (\(projectDir.lastPathComponent))", #selector(chooseFolder)))
        m.addItem(.separator())
        let quit = NSMenuItem(title: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        m.addItem(quit)
    }

    func menuWillOpen(_ m: NSMenu) { refresh() }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
