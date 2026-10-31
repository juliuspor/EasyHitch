import SwiftUI

extension View {
    /// Liquid Glass on iOS 26 and later, a material on older systems. A `tint` colours the
    /// glass, as on a pin that carries a station's availability, and `interactive` glass
    /// answers a touch the way iOS 26 controls do.
    @ViewBuilder
    func glassBackground(in shape: some Shape, tint: Color? = nil, interactive: Bool = false) -> some View {
        if #available(iOS 26, *) {
            glassEffect(.regular.tint(tint).interactive(interactive), in: shape)
        } else if let tint {
            background(tint.gradient, in: shape)
        } else {
            background(.regularMaterial, in: shape)
        }
    }

    @ViewBuilder
    func prominentGlassButton() -> some View {
        if #available(iOS 26, *) {
            buttonStyle(.glassProminent)
        } else {
            buttonStyle(.borderedProminent)
        }
    }

    @ViewBuilder
    func glassButton() -> some View {
        if #available(iOS 26, *) {
            buttonStyle(.glass)
        } else {
            buttonStyle(.bordered)
        }
    }
}

/// Glass shapes inside blend into each other as they come close, as the controls along an edge
/// do on iOS 26, and share one sampling of what lies behind them. Older systems just stack them.
struct GlassGroup<Content: View>: View {
    var spacing: CGFloat = 12
    @ViewBuilder let content: Content

    var body: some View {
        if #available(iOS 26, *) {
            GlassEffectContainer(spacing: spacing) { content }
        } else {
            content
        }
    }
}
