import MapKit
import SwiftUI

struct StationScreen: View {
    let station: Station
    @Environment(StationStore.self) private var store
    @State private var lookAround: MKLookAroundScene?
    @State private var showLookAround = false

    private var detail: StationDetail? { store.details[station.id] }

    var body: some View {
        let racks = detail?.racks ?? []
        ZStack {
            Color(hex: 0xE6EDF1).ignoresSafeArea()
            if !racks.isEmpty {
                SpotView(stationID: station.id, racks: racks, from: Backend.rider)
                    .ignoresSafeArea()
            } else {
                ProgressView("Loading station")
            }
        }
        .safeAreaInset(edge: .bottom) {
            StatusCard(station: detail?.station ?? station)
                .padding(.horizontal, 12)
        }
        .navigationTitle(station.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if lookAround != nil {
                Button { showLookAround = true } label: {
                    Label("Look Around", systemImage: "binoculars.fill")
                        .labelStyle(.titleAndIcon)
                }
            }
        }
        .lookAroundViewer(isPresented: $showLookAround, initialScene: lookAround)
        .task {
            // Apple's street-level imagery nearest the station. Nil where Apple has none or the
            // phone is offline, which keeps the button hidden instead of opening an empty viewer.
            lookAround = try? await MKLookAroundSceneRequest(coordinate: station.coordinate).scene
        }
        .task { await store.pollDetail(station.id) }
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
