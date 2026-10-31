import SwiftUI

/// Endress+Hauser colors, taken from endress.com.
enum Brand {
    /// Logo blue: the app's accent and main actions.
    static let blue = Color(hex: 0x00AEEF)
    /// Free spots, on the map, in the card and in the 3D view (Spot/spot.js uses the same
    /// value). Free and taken never rely on colour alone: the pins and card carry the count,
    /// and in 3D a taken slot holds a bike while a free one glows.
    static let free = Color(hex: 0x19C25A)
    /// Dark slate used for text and icons on endress.com.
    static let slate = Color(hex: 0x36444C)
    /// Light slate for inactive states.
    static let mist = Color(hex: 0xA4B3BC)
    /// The rider's location dot and route, Apple Maps' blue (Spot/spot.js uses the same value).
    static let location = Color(hex: 0x007AFF)
    static let red = Color(hex: 0xD50C2F)
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }
}
