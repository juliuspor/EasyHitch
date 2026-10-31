import CoreLocation
import SwiftUI

enum Site {
    /// Middle of the Endress+Hauser block in Reinach BL (Kägenstrasse to Christoph-Merian-Ring),
    /// so the map opens with all its bike stations in view.
    static let center = CLLocationCoordinate2D(latitude: 47.48776, longitude: 7.59908)
}

// The Availability API's shapes (documentation/api/availability.openapi.json). Unknown keys,
// such as `distance_m`, are ignored.

struct Location: Codable, Hashable {
    let lat: Double
    let lon: Double

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    func distance(to other: Location) -> CLLocationDistance {
        CLLocation(latitude: lat, longitude: lon).distance(from: CLLocation(latitude: other.lat, longitude: other.lon))
    }
}

/// A station with how many of its slots are free, taken, or not seen by a camera recently.
struct Station: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let location: Location
    let capacity: Int
    let free: Int
    let taken: Int
    let unknown: Int
    /// The latest camera report, nil before the first.
    let updatedAt: Date?

    var coordinate: CLLocationCoordinate2D { location.coordinate }
    /// A camera has seen at least one slot recently, so the free count means something.
    var reporting: Bool { free + taken > 0 }
    var availability: Availability { Availability(free: free, taken: taken, unknown: unknown) }
}

enum SlotState: String, Codable {
    case free, taken, unknown
}

struct Slot: Codable, Identifiable, Hashable {
    let number: Int
    let state: SlotState
    let location: Location
    let changedAt: Date?

    var id: Int { number }
}

/// A station with the state of every slot (`GET /v1/stations/{id}`).
struct StationDetail: Decodable {
    let station: Station
    let slots: [Slot]

    private enum CodingKeys: String, CodingKey {
        case slots
    }

    init(station: Station, slots: [Slot]) {
        self.station = station
        self.slots = slots
    }

    /// The API sends the station's fields and its slots side by side.
    init(from decoder: Decoder) throws {
        station = try Station(from: decoder)
        slots = try decoder.container(keyedBy: CodingKeys.self).decode([Slot].self, forKey: .slots)
    }

    /// The slots in their racks: a station can have several racks, for example on two sides of
    /// a building. Slots are numbered along each rack, so a jump of more than two metres between
    /// one number and the next starts a new rack.
    var racks: [[Slot]] {
        slots.sorted { $0.number < $1.number }.reduce(into: []) { racks, slot in
            if let last = racks.last?.last, last.location.distance(to: slot.location) < 2 {
                racks[racks.count - 1].append(slot)
            } else {
                racks.append([slot])
            }
        }
    }
}

enum Availability {
    /// Any free slot counts as available; the number on the pin says how many. With no free
    /// slot but some not seen recently, the station may have room, so it is unknown, not full.
    case available, full, unknown

    init(free: Int, taken: Int, unknown: Int) {
        if free > 0 {
            self = .available
        } else if taken > 0 && unknown == 0 {
            self = .full
        } else {
            self = .unknown
        }
    }

    var color: Color {
        switch self {
        case .available: Brand.free
        case .full: Brand.red
        case .unknown: Brand.mist
        }
    }
}
