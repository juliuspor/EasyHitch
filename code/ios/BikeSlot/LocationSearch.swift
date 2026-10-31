import MapKit
import SwiftUI

/// A place the user searched for, e.g. the building they are cycling to.
struct Destination: Equatable {
    let name: String
    let coordinate: CLLocationCoordinate2D

    static func == (a: Destination, b: Destination) -> Bool {
        a.name == b.name && a.coordinate.latitude == b.coordinate.latitude
            && a.coordinate.longitude == b.coordinate.longitude
    }

    func distance(to station: Station) -> CLLocationDistance {
        CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
            .distance(from: CLLocation(latitude: station.location.lat, longitude: station.location.lon))
    }
}

/// Address and place suggestions from Apple Maps, biased towards the site.
@MainActor
@Observable
final class LocationSearch: NSObject, MKLocalSearchCompleterDelegate {
    var query = "" {
        didSet { query.isEmpty ? (completions = []) : (completer.queryFragment = query) }
    }
    private(set) var completions: [MKLocalSearchCompletion] = []
    @ObservationIgnored private let completer = MKLocalSearchCompleter()

    override init() {
        super.init()
        completer.delegate = self
        completer.resultTypes = [.address, .pointOfInterest]
        completer.region = MKCoordinateRegion(center: Site.center, latitudinalMeters: 20_000,
                                              longitudinalMeters: 20_000)
    }

    nonisolated func completerDidUpdateResults(_ completer: MKLocalSearchCompleter) {
        let results = Array(completer.results.prefix(6))
        Task { @MainActor in
            if !self.query.isEmpty { self.completions = results }
        }
    }

    nonisolated func completer(_ completer: MKLocalSearchCompleter, didFailWithError error: Error) {}

    func resolve(_ completion: MKLocalSearchCompletion) async -> Destination? {
        guard let item = try? await MKLocalSearch(request: MKLocalSearch.Request(completion: completion))
            .start().mapItems.first else { return nil }
        let coordinate: CLLocationCoordinate2D
        if #available(iOS 26, *) {
            coordinate = item.location.coordinate
        } else {
            coordinate = item.placemark.coordinate
        }
        return Destination(name: completion.title, coordinate: coordinate)
    }
}

/// Floating search field with station and place suggestions underneath.
struct SearchOverlay: View {
    @Bindable var search: LocationSearch
    var focused: FocusState<Bool>.Binding
    let stations: [Station]
    let openStation: (Station) -> Void
    let choose: (MKLocalSearchCompletion) -> Void

    private var matchingStations: [Station] {
        stations.filter { $0.name.localizedCaseInsensitiveContains(search.query) }
    }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
            TextField("Search a building or address", text: $search.query)
                .focused(focused)
                .submitLabel(.search)
                .autocorrectionDisabled()
                .onSubmit { if let first = search.completions.first { choose(first) } }
            if !search.query.isEmpty {
                Button { search.query = "" } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary)
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
        .glassBackground(in: Capsule())
        // An overlay, so the list floats over the map instead of resizing its safe area.
        .overlay(alignment: .top) {
            if focused.wrappedValue && !search.query.isEmpty {
                results
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 54)
            }
        }
    }

    private var results: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(matchingStations) { station in
                row(icon: "bicycle", tint: station.availability.color, title: station.name,
                    subtitle: "\(station.free) of \(station.capacity) spots free") { openStation(station) }
            }
            ForEach(search.completions, id: \.self) { completion in
                row(icon: "mappin.circle.fill", tint: Brand.blue, title: completion.title,
                    subtitle: completion.subtitle) { choose(completion) }
            }
            if matchingStations.isEmpty && search.completions.isEmpty {
                Text("No results")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(14)
            }
        }
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private func row(icon: String, tint: Color, title: String, subtitle: String,
                     action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(tint)
                    .frame(width: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.subheadline.weight(.semibold))
                    if !subtitle.isEmpty {
                        Text(subtitle).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Spacer()
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}
