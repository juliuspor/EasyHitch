import SwiftUI

@main
struct BikeSlotApp: App {
    @State private var store = StationStore()

    var body: some Scene {
        WindowGroup {
            MapScreen()
                .environment(store)
                .tint(Brand.blue)
                .task { await store.pollStations() }
        }
    }
}
