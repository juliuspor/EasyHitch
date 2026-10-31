import Foundation

/// Built-in sample stations so the app runs without a backend. Every few seconds a random
/// slot is taken or freed, so the UI has live changes to show; slots no camera saw in the
/// sample stay unknown, and a station's last free slot stays free, so the demo rider always
/// has a spot to navigate to. Refresh the data with code/ios/refresh-demo.sh.
actor DemoService: StationService {
    static let shared = DemoService()
    /// A rider on Christoph-Merian-Ring, just past the corner with Kägenstrasse, cycling east in
    /// the bike lane towards the south station.
    static let rider = Location(lat: 47.4867629, lon: 7.5981029)

    private var details: [StationDetail]
    private var lastStep = Date()
    private static let stepSeconds = 4.0

    init() {
        let url = Bundle.main.url(forResource: "demo-stations", withExtension: "json")
        let data = url.flatMap { try? Data(contentsOf: $0) } ?? Data("[]".utf8)
        let loaded = (try? APIClient.decoder.decode([StationDetail].self, from: data)) ?? []
        details = loaded.map { $0.with(slots: $0.slots, at: Date()) }
    }

    func stations() async throws -> [Station] {
        advance()
        return details.map(\.station)
    }

    func station(_ id: String) async throws -> StationDetail {
        advance()
        guard let detail = details.first(where: { $0.station.id == id }) else { throw URLError(.fileDoesNotExist) }
        return detail
    }

    private func advance() {
        let steps = Int(Date().timeIntervalSince(lastStep) / Self.stepSeconds)
        guard steps > 0, !details.isEmpty else { return }
        lastStep.addTimeInterval(Double(steps) * Self.stepSeconds)
        for _ in 0..<min(steps, 10) {
            let station = Int.random(in: details.indices)
            var slots = details[station].slots
            guard let index = slots.indices.filter({ slots[$0].state != .unknown }).randomElement() else { continue }
            let slot = slots[index]
            if slot.state == .free && slots.filter({ $0.state == .free }).count == 1 { continue }
            slots[index] = Slot(number: slot.number, state: slot.state == .free ? .taken : .free,
                                location: slot.location, changedAt: Date())
            details[station] = details[station].with(slots: slots, at: Date())
        }
    }
}

private extension StationDetail {
    /// The same station with new slot states, counted as the backend counts them.
    func with(slots: [Slot], at date: Date) -> StationDetail {
        let old = station
        let count = { (state: SlotState) in slots.filter { $0.state == state }.count }
        let station = Station(id: old.id, name: old.name, location: old.location, capacity: slots.count,
                              free: count(.free), taken: count(.taken), unknown: count(.unknown), updatedAt: date)
        return StationDetail(station: station, slots: slots)
    }
}
