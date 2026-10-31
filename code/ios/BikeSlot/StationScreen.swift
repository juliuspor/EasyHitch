import MapKit
import SwiftUI

/// A station in 3D, laid over the map once the map has leaned in towards it: the rack with a
/// bike on every taken slot, the free count underneath, and the way back to the map. With a
/// rider it starts in the rider's own view at street level and rides from there.
///
/// It stays over the map with no station, invisible, so its 3D page is loaded before the first
/// station opens (see `SpotView`).
struct StationScreen: View {
    let station: Station?
    let rider: Location?
    /// The map has finished leaning in. The controls show then, and the 3D view fades in as
    /// soon as it has drawn its first frame, then starts its way in.
    let arrived: Bool
    let close: () -> Void
    @Environment(StationStore.self) private var store
    @State private var drawn = false
    @State private var lookAround: MKLookAroundScene?
    @State private var showLookAround = false

    private var detail: StationDetail? { station.flatMap { store.details[$0.id] } }
    private var shown: Bool { station != nil && arrived && drawn }

    var body: some View {
        ZStack {
            SpotView(stationID: station?.id, racks: detail?.racks ?? [], from: rider, go: shown,
                     ready: { drawn = true })
                .ignoresSafeArea()
                .opacity(shown ? 1 : 0)
                // As long as the map's push into the street, which runs with `arrived`.
                .animation(.easeInOut(duration: 0.6), value: shown)
                .allowsHitTesting(shown)
                .accessibilityHidden(!shown)
            if let station {
                if arrived && !drawn {
                    ProgressView()
                        .padding(14)
                        .glassBackground(in: Circle())
                }
                Color.clear
                    .safeAreaInset(edge: .top) { controls(topBar(station)) }
                    .safeAreaInset(edge: .bottom) { controls(StatusCard(station: detail?.station ?? station)) }
            }
        }
        .lookAroundViewer(isPresented: $showLookAround, initialScene: lookAround)
        .onChange(of: station?.id) { drawn = false }
        .task(id: station?.id) {
            // Apple's street-level imagery nearest the station. Nil where Apple has none or the
            // phone is offline, which keeps the button hidden instead of opening an empty viewer.
            lookAround = nil
            guard let station else { return }
            lookAround = try? await MKLookAroundSceneRequest(coordinate: station.coordinate).scene
        }
        .task(id: station?.id) {
            if let id = station?.id { await store.pollDetail(id) }
        }
    }

    private func controls(_ content: some View) -> some View {
        content
            .padding(.horizontal, 12)
            .opacity(arrived ? 1 : 0)
            .allowsHitTesting(arrived)
    }

    private func topBar(_ station: Station) -> some View {
        GlassGroup {
            HStack(spacing: 8) {
                circleButton("chevron.left", label: "Back to the map", action: close)
                Spacer(minLength: 0)
                Text(station.name)
                    .font(.headline)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                    .padding(.horizontal, 16)
                    .frame(height: 44)
                    .glassBackground(in: Capsule())
                Spacer(minLength: 0)
                if lookAround != nil {
                    circleButton("binoculars.fill", label: "Look Around") { showLookAround = true }
                } else {
                    // Keeps the name centred.
                    Color.clear.frame(width: 44, height: 44)
                }
            }
        }
    }

    private func circleButton(_ symbol: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.body.weight(.semibold))
                .frame(width: 44, height: 44)
                .glassBackground(in: Circle(), interactive: true)
                // The whole circle, not just the glyph: a thin chevron alone loses a tap
                // beside it to the 3D view underneath.
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

private struct StatusCard: View {
    let station: Station

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(station.reporting ? "\(station.free)" : "–")
                    .font(.system(size: 44, weight: .bold, design: .rounded).monospacedDigit())
                    .foregroundStyle(station.availability.color)
                    .contentTransition(.numericText())
                Text("of \(station.capacity) spots free")
                    .font(.headline)
                    .foregroundStyle(.secondary)
                Spacer()
            }
            .animation(.snappy, value: station.free)

            if !station.reporting {
                Label(station.updatedAt == nil ? "No camera at this station yet" : "No camera has seen this station recently",
                      systemImage: "video.slash")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            } else if station.unknown > 0 {
                Label("\(station.unknown) spots not seen by a camera recently", systemImage: "eye.slash")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

        }
        .padding(16)
        .glassBackground(in: RoundedRectangle(cornerRadius: 28, style: .continuous))
    }
}
