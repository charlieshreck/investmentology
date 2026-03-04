import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useStore } from "../../stores/useStore";

const STEPS = [
  {
    title: "Welcome to Haute Banque",
    subtitle: "Your AI-powered investment advisor",
    body: "9 AI agents analyze stocks using institutional-grade frameworks — from Greenblatt's Magic Formula to Munger's cognitive bias checklist.",
  },
  {
    title: "The Pipeline",
    subtitle: "6 layers of analysis",
    body: "L1 Quant Gate screens 5,000+ stocks. L2 Competence checks your circle. L3 Multi-Agent debate. L4 Adversarial review. L5 Timing & Sizing. L6 Continuous Learning.",
  },
  {
    title: "Key Features",
    subtitle: "Everything you need",
    body: "Portfolio tracking with real-time P&L. Watchlist monitoring. Deep-dive analysis on any stock. Risk management with drawdown tracking and VaR.",
  },
  {
    title: "Paper Trading Only",
    subtitle: "Learn without risk",
    body: "All positions are paper trades. No real money is involved. Build your track record and calibrate your decision-making before risking capital.",
  },
];

export function OnboardingFlow() {
  const [step, setStep] = useState(0);
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);

  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        background: "var(--color-bg)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-2xl)",
      }}
    >
      {/* Skip button */}
      <button
        onClick={() => setHasSeenOnboarding(true)}
        style={{
          position: "absolute",
          top: "var(--space-xl)",
          right: "var(--space-xl)",
          background: "none",
          border: "none",
          color: "var(--color-text-muted)",
          fontSize: "var(--text-sm)",
          cursor: "pointer",
          fontWeight: 500,
        }}
      >
        Skip
      </button>

      {/* Content */}
      <div style={{ maxWidth: 360, width: "100%", textAlign: "center" }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            <div style={{
              fontSize: "var(--text-2xl)",
              fontWeight: 800,
              marginBottom: "var(--space-sm)",
              background: "linear-gradient(135deg, var(--color-accent), var(--color-success))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}>
              {current.title}
            </div>
            <div style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-text-muted)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "var(--space-xl)",
            }}>
              {current.subtitle}
            </div>
            <div style={{
              fontSize: "var(--text-md)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.6,
            }}>
              {current.body}
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Step dots */}
        <div style={{
          display: "flex",
          gap: 6,
          justifyContent: "center",
          margin: "var(--space-2xl) 0",
        }}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              style={{
                width: i === step ? 20 : 6,
                height: 6,
                borderRadius: "var(--radius-full)",
                background: i === step ? "var(--color-accent)" : "var(--color-surface-2)",
                transition: "all 0.3s ease",
              }}
            />
          ))}
        </div>

        {/* Action button */}
        <button
          onClick={() => {
            if (isLast) {
              setHasSeenOnboarding(true);
            } else {
              setStep((s) => s + 1);
            }
          }}
          style={{
            width: "100%",
            padding: "var(--space-md) var(--space-xl)",
            background: isLast
              ? "linear-gradient(135deg, var(--color-accent), var(--color-success))"
              : "var(--color-surface-1)",
            border: isLast ? "none" : "1px solid var(--glass-border)",
            borderRadius: "var(--radius-md)",
            color: isLast ? "#fff" : "var(--color-text)",
            fontSize: "var(--text-sm)",
            fontWeight: 700,
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          {isLast ? "Get Started" : "Next"}
        </button>
      </div>
    </motion.div>
  );
}
