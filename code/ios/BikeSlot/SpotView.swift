import SwiftUI
import WebKit

/// The 3D view of one station: Spot/spot.html (three.js) flies down into a model of the
/// Endress+Hauser block and lands in front of the station's rack, with a green pad on
/// every free slot, a bike on every taken one, and a grey pad where no camera has looked
/// recently. Once landed you look around it like in Google Maps 3D (drag, pinch, twist); the
/// page handles those gestures, so the web view must not scroll or zoom.
///
/// Loading the page means parsing three.js and the models, which would stall whatever moves on
/// screen at the time, so the view stays mounted with no station and loads ahead: a station
/// then only has to be built. Once the station is gone, the page reloads for the next one.
struct SpotView: UIViewRepresentable {
    /// The station to show, or nil to keep the page loaded and idle.
    let stationID: String?
    /// The station's slots by rack, as `StationDetail.racks` groups them.
    let racks: [[Slot]]
    /// The rider's position: given one, the view rides from the rider's own view along the
    /// streets instead of flying in from above.
    let from: Location?
    /// Whether the way in may start. Until then the page holds its first frame, so it can
    /// fade in before anything moves.
    let go: Bool
    /// Called once the page has drawn that first frame.
    let ready: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(context.coordinator, name: "spot")
        let web = WKWebView(frame: .zero, configuration: configuration)
        web.isOpaque = false
        web.backgroundColor = .clear
        web.scrollView.isScrollEnabled = false
        web.scrollView.bounces = false
        web.scrollView.pinchGestureRecognizer?.isEnabled = false
        // The page draws edge to edge behind the bars; SwiftUI already handles the safe area.
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.navigationDelegate = context.coordinator
        if let folder = Bundle.main.url(forResource: "Spot", withExtension: nil) {
            web.loadFileURL(folder.appendingPathComponent("spot.html"), allowingReadAccessTo: folder)
        }
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {
        context.coordinator.state = (stationID, racks, from)
        context.coordinator.ready = ready
        context.coordinator.flush(web)
        if go { context.coordinator.start(web) }
    }

    /// The content controller keeps its handlers, so let go of the coordinator with the view.
    static func dismantleUIView(_ web: WKWebView, coordinator: Coordinator) {
        web.configuration.userContentController.removeScriptMessageHandler(forName: "spot")
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var state: (stationID: String?, racks: [[Slot]], from: Location?)?
        var ready: () -> Void = {}
        private var loaded = false
        private var started = false
        /// The station the page shows, and the slots it was last sent.
        private var shown: String?
        private var sentSlots: [Slot]?

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            loaded = true
            flush(webView)
        }

        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
            if message.body as? String == "ready" { ready() }
        }

        /// The racks are built once; later changes only update the slots.
        func flush(_ web: WKWebView) {
            guard loaded, let state else { return }
            if let shown, shown != state.stationID {
                // A page builds one station, so start a fresh one for whatever comes next.
                self.shown = nil
                sentSlots = nil
                started = false
                loaded = false
                web.reload()
                return
            }
            guard let stationID = state.stationID, !state.racks.isEmpty else { return }
            let slots = state.racks.flatMap { $0 }
            guard slots != sentSlots else { return }
            let script: String
            if sentSlots == nil {
                let numbers = state.racks.map { $0.map(\.number) }
                script = "BikeSpot.show({id: \(Self.json(stationID)), slots: \(Self.json(slots)), "
                    + "racks: \(Self.json(numbers)), from: \(Self.json(state.from))})"
                shown = stationID
            } else {
                script = "BikeSpot.update(\(Self.json(slots)))"
            }
            sentSlots = slots
            web.evaluateJavaScript(script)
        }

        func start(_ web: WKWebView) {
            guard !started, sentSlots != nil else { return }
            started = true
            web.evaluateJavaScript("BikeSpot.go()")
        }

        /// JSON text of a value, safe to paste into a script.
        private static func json(_ value: some Encodable) -> String {
            (try? JSONEncoder().encode(value)).flatMap { String(data: $0, encoding: .utf8) } ?? "null"
        }
    }
}
