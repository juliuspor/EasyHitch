import MapKit
import SwiftUI

struct StationScreen: View {
    let station: Station
    @Environment(StationStore.self) private var store
    @State private var lookAround: MKLookAroundScene?
    @State private var showLookAround = false
    /// The rack the 3D view stands in front of.
    @State private var rack = 0

    private var detail: StationDetail? { store.details[station.id] }

    var body: some View {
        let racks = detail?.racks ?? []
        ZStack {
            Color(hex: 0xE6EDF1).ignoresSafeArea()
            if !racks.isEmpty {
                SpotView(stationID: station.id, racks: racks, rack: rack)
                    .ignoresSafeArea()
            } else {
                ProgressView("Loading station")
            }
        }
        .safeAreaInset(edge: .bottom) {
            VStack(alignment: .trailing, spacing: 6) {
                // The 3D world is built from OpenStreetMap data (ODbL).
                Text("Map data © OpenStreetMap contributors")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 8)
                StatusCard(station: detail?.station ?? station, racks: racks, rack: $rack)
            }
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
    let racks: [[Slot]]
    @Binding var rack: Int

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

            // A station on two sides of a building has a rack on each; the 3D view shows one at a time.
            if racks.count > 1 {
                HStack(spacing: 8) {
                    ForEach(racks.indices, id: \.self) { index in
                        RackButton(slots: racks[index], selected: index == rack) { rack = index }
                    }
                }
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}

private struct RackButton: View {
    let slots: [Slot]
    let selected: Bool
    let action: () -> Void

    private static let shape = RoundedRectangle(cornerRadius: 14, style: .continuous)

    var body: some View {
        let count = { (state: SlotState) in slots.filter { $0.state == state }.count }
        let availability = Availability(free: count(.free), taken: count(.taken), unknown: count(.unknown))
        Button(action: action) {
            HStack(spacing: 8) {
                Circle()
                    .fill(availability.color)
                    .frame(width: 8, height: 8)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Slots \(slots.first?.number ?? 0)–\(slots.last?.number ?? 0)")
                        .font(.footnote.weight(.semibold))
                    Text("\(count(.free)) free")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .contentTransition(.numericText())
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(selected ? Brand.blue.opacity(0.14) : Color.primary.opacity(0.05), in: Self.shape)
            .overlay(Self.shape.stroke(selected ? Brand.blue : .clear, lineWidth: 1.5))
            .contentShape(Self.shape)
        }
        .buttonStyle(.plain)
        .animation(.snappy, value: selected)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}
