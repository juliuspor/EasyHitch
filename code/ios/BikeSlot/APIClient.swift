import Foundation

/// Everything the app needs from a backend: the Availability API, documented in
/// documentation/api/availability.openapi.json (generated from code/backend/availability).
protocol StationService: Sendable {
    func stations() async throws -> [Station]
    func station(_ id: String) async throws -> StationDetail
}

enum Backend {
    /// The live backend, or the built-in demo data when `demoMode` is on
    /// (Settings, or the launch argument `-demoMode YES`).
    static var current: any StationService {
        UserDefaults.standard.bool(forKey: "demoMode") ? DemoService.shared : APIClient()
    }

    /// Where the rider is, for the blue dot on the map and the start of the 3D navigation. The
    /// demo has one; the live app has none, because it does not ask for the phone's location.
    static var rider: Location? {
        UserDefaults.standard.bool(forKey: "demoMode") ? DemoService.rider : nil
    }
}

/// Talks to the Availability API. The base URL can be changed in the app.
struct APIClient: StationService {
    /// Debug builds carry the address of the Mac that built them (set in project.yml),
    /// so a phone finds the backend on that Mac without typing an IP.
    static let defaultURL = Bundle.main.url(forResource: "backend-url", withExtension: "txt")
        .flatMap { try? String(contentsOf: $0, encoding: .utf8) }?
        .trimmingCharacters(in: .whitespacesAndNewlines) ?? "http://localhost:8000"

    static var baseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "backendURL") ?? defaultURL
        return URL(string: stored) ?? URL(string: defaultURL)!
    }

    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        // ISO 8601 times, with or without fractions of a second.
        decoder.dateDecodingStrategy = .custom { decoder in
            let text = try decoder.singleValueContainer().decode(String.self)
            for style in [Date.ISO8601FormatStyle(), Date.ISO8601FormatStyle(includingFractionalSeconds: true)] {
                if let date = try? style.parse(text) { return date }
            }
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath, debugDescription: "not ISO 8601: \(text)"))
        }
        return decoder
    }()

    private struct StationList: Decodable {
        let stations: [Station]
    }

    func stations() async throws -> [Station] {
        let list: StationList = try await get("/v1/stations")
        return list.stations
    }

    func station(_ id: String) async throws -> StationDetail {
        try await get("/v1/stations/\(id)")
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let (data, response) = try await URLSession.shared.data(from: Self.baseURL.appendingPathComponent(path))
        try Self.check(response)
        return try Self.decoder.decode(T.self, from: data)
    }

    private static func check(_ response: URLResponse) throws {
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw URLError(.badServerResponse)
        }
    }
}
