// Countertop List Sync: sends one Apple Reminders list to a Countertop dashboard server whenever it changes.
// Runs as a background app (no Dock icon). EventKit tells it about every change, including ones made on an
// iPhone or with Siri that arrive through iCloud, so the dashboard updates within a few seconds.
//
// Settings live in the app's defaults (build.sh asks for them):
//   defaults write local.countertop.listsync server "http://192.168.1.50:8090"
//   defaults write local.countertop.listsync key    "<sync key from Controls > Setup > Lists>"
//   defaults write local.countertop.listsync list   "Grocery"
import AppKit
import EventKit
import Foundation

let defaults = UserDefaults.standard      // the app's own domain: local.countertop.listsync
let store = EKEventStore()
var pending: DispatchWorkItem?
var lastSent = ""

func log(_ s: String) {
    let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
    print("\(f.string(from: Date()))  \(s)"); fflush(stdout)
}

func setting(_ k: String) -> String { (defaults.string(forKey: k) ?? "").trimmingCharacters(in: .whitespacesAndNewlines) }

func send(_ items: [[String: String]], force: Bool) {
    let server = setting("server"), key = setting("key")
    guard !server.isEmpty, !key.isEmpty, let url = URL(string: server.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/lists/push") else {
        log("not set up: run build.sh again, or set server and key with defaults write"); return
    }
    let body: [String: Any] = ["key": key, "items": items, "via": "Reminders"]
    guard let data = try? JSONSerialization.data(withJSONObject: body, options: [.sortedKeys]) else { return }
    let sig = String(decoding: data, as: UTF8.self)
    if sig == lastSent && !force { return }
    var req = URLRequest(url: url, timeoutInterval: 15)
    req.httpMethod = "POST"
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    req.httpBody = data
    URLSession.shared.dataTask(with: req) { resp, r, err in
        let code = (r as? HTTPURLResponse)?.statusCode ?? 0
        DispatchQueue.main.async {
            if code == 200 { lastSent = sig; log("sent \(items.count) items") }
            else { log("send failed (\(code)): \(err?.localizedDescription ?? String(decoding: resp ?? Data(), as: UTF8.self))") }
        }
    }.resume()
}

func sync(force: Bool = false) {
    let name = setting("list").isEmpty ? "Grocery" : setting("list")
    let cals = store.calendars(for: .reminder).filter { $0.title == name }
    if cals.isEmpty { log("no Reminders list named \"\(name)\""); return }
    let pred = store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: nil, calendars: cals)
    store.fetchReminders(matching: pred) { rems in
        let sorted = (rems ?? []).sorted { ($0.creationDate ?? .distantPast) < ($1.creationDate ?? .distantPast) }
        let items = sorted.compactMap { r -> [String: String]? in
            let t = (r.title ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            return t.isEmpty ? nil : ["id": r.calendarItemIdentifier, "text": t]
        }
        DispatchQueue.main.async { send(items, force: force) }
    }
}

// changes often come in bursts (iCloud sync, ticking several items): wait for things to settle
func soon() {
    pending?.cancel()
    let w = DispatchWorkItem { sync() }
    pending = w
    DispatchQueue.main.asyncAfter(deadline: .now() + 2, execute: w)
}

func start() {
    NotificationCenter.default.addObserver(forName: .EKEventStoreChanged, object: store, queue: .main) { _ in soon() }
    // safety net: resend every 10 minutes even if nothing changed (covers server restarts)
    Timer.scheduledTimer(withTimeInterval: 600, repeats: true) { _ in sync(force: true) }
    log("watching Reminders list \"\(setting("list").isEmpty ? "Grocery" : setting("list"))\" -> \(setting("server"))")
    sync(force: true)
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let granted: (Bool, Error?) -> Void = { ok, err in
    DispatchQueue.main.async {
        if ok { start() }
        else { log("no access to Reminders: allow it in System Settings > Privacy & Security > Reminders. \(err?.localizedDescription ?? "")"); exit(1) }
    }
}
if #available(macOS 14.0, *) {
    store.requestFullAccessToReminders(completion: granted)
} else {
    store.requestAccess(to: .reminder, completion: granted)
}
app.run()
