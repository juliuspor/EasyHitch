import SwiftUI
import WebKit

/// The 3D view of one station: Spot/spot.html (three.js) flies down into a model of the
/// Endress+Hauser block and lands in front of the station's rack, with a green pad on
/// every free slot, a bike on every taken one, and a grey pad where no camera has looked
/// recently. Once landed you look around it like in Google Maps 3D (drag, pinch, twist); the
/// page handles those gestures, so the web view must not scroll or zoom, and a sideways drag
/// must not pop the screen.
struct SpotView: UIViewRepresentable {
    let stationID: String
    /// The station's slots by rack, as `StationDetail.racks` groups them.
    let racks: [[Slot]]
    /// The rider's position: given one, the view navigates from it along the streets instead
    /// of flying in from above.
    let from: Location?

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let web = GestureWebView(frame: .zero, configuration: WKWebViewConfiguration())
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
        context.coordinator.flush(web)
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate {
        var state: (stationID: String, racks: [[Slot]], from: Location?)?
        private var loaded = false
        private var sentSlots: [Slot]?

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            loaded = true
            flush(webView)
        }

        /// The racks are built once; later changes only update the slots.
        func flush(_ web: WKWebView) {
            guard loaded, let state, !state.racks.isEmpty else { return }
            let slots = state.racks.flatMap { $0 }
            guard slots != sentSlots else { return }
            let script: String
            if sentSlots == nil {
                let numbers = state.racks.map { $0.map(\.number) }
                script = "BikeSpot.show({id: \(Self.json(state.stationID)), slots: \(Self.json(slots)), "
                    + "racks: \(Self.json(numbers)), from: \(Self.json(state.from))})"
            } else {
                script = "BikeSpot.update(\(Self.json(slots)))"
            }
            sentSlots = slots
            web.evaluateJavaScript(script)
        }

        /// JSON text of a value, safe to paste into a script.
        private static func json(_ value: some Encodable) -> String {
            (try? JSONEncoder().encode(value)).flatMap { String(data: $0, encoding: .utf8) } ?? "null"
        }
    }
}

/// A web view that keeps the navigation stack's swipe-back gestures off while it is on screen,
/// so dragging the 3D view sideways turns it instead of closing the screen. The back button
/// still works.
final class GestureWebView: WKWebView {
    private weak var navigation: UINavigationController?

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window != nil {
            navigation = sequence(first: self as UIResponder, next: \.next)
                .compactMap { ($0 as? UIViewController)?.navigationController }.first
            setSwipeBack(enabled: false)
        } else {
            setSwipeBack(enabled: true)
        }
    }

    private func setSwipeBack(enabled: Bool) {
        navigation?.interactivePopGestureRecognizer?.isEnabled = enabled
        if #available(iOS 26.0, *) {
            // iOS 26 also pops when swiping anywhere in the content, not only from the edge.
            navigation?.interactiveContentPopGestureRecognizer?.isEnabled = enabled
        }
    }
}
