import Cocoa

class Fixture: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    let status = NSTextField(string: "Ready")
    let titleField = NSTextField(string: "")
    func applicationDidFinishLaunching(_ note: Notification) {
        window = NSWindow(contentRect: NSRect(x: 80, y: 80, width: 360, height: 180), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = "Hermes Jev Test Fixture"
        status.frame = NSRect(x: 24, y: 120, width: 300, height: 24)
        status.setAccessibilityLabel("Status")
        titleField.frame = NSRect(x: 24, y: 80, width: 300, height: 24)
        titleField.setAccessibilityLabel("Title")
        let button = NSButton(title: "Complete", target: self, action: #selector(complete))
        button.frame = NSRect(x: 24, y: 24, width: 120, height: 32)
        button.setAccessibilityLabel("Complete")
        window.contentView!.addSubview(status)
        window.contentView!.addSubview(titleField)
        window.contentView!.addSubview(button)
        window.orderBack(nil)
    }
    @objc func complete() { status.stringValue = "Done" }
}
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let fixture = Fixture()
app.delegate = fixture
app.run()
