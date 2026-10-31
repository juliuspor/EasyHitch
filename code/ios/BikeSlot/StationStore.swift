import Foundation
import Observation

/// Polls the backend and holds the latest state for the map and station screens.
@MainActor
@Observable
final class StationStore {
    var stations: [Station] = []
    var details: [String: StationDetail] = [:]
    var errorMessage: String?

    private var api: any StationService { Backend.current }

    /// Slots no camera has seen recently are unknown, so they count neither as free nor as taken.
    var totalFree: Int { stations.reduce(0) { $0 + $1.free } }

    func pollStations() async {
        while !Task.isCancelled {
            do {
                stations = try await api.stations()
                errorMessage = nil
            } catch {
                errorMessage = "No backend at \(APIClient.baseURL.host() ?? "?")"
            }
            try? await Task.sleep(for: .seconds(2))
        }
    }

    func pollDetail(_ id: String) async {
        while !Task.isCancelled {
            if let detail = try? await api.station(id) {
                details[id] = detail
            }
            try? await Task.sleep(for: .seconds(1.5))
        }
    }
}
