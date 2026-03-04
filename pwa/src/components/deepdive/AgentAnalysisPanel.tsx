import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CollapsiblePanel } from "./CollapsiblePanel";
import { AgentConsensusPanel } from "../shared/AgentConsensusPanel";
import { SignalTagCloud } from "../shared/SignalTagCloud";
import { Badge } from "../shared/Badge";
import { FormattedProse } from "../shared/FormattedProse";
import { voteColor, voteLabel } from "../../utils/deepdiveHelpers";
import { verdictColor, verdictLabel } from "../../utils/verdictHelpers";
import type { VerdictData } from "../../views/StockDeepDive";

function VoteTallyPreview({ opinions }: { opinions: VerdictData["advisoryOpinions"] }) {
  if (!opinions?.length) return null;
  const tally = { approve: 0, veto: 0, adjust: 0 };
  for (const op of opinions) {
    if (op.vote === "APPROVE") tally.approve++;
    else if (op.vote === "VETO") tally.veto++;
    else tally.adjust++;
  }
  return (
    <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", display: "inline-flex", gap: "var(--space-sm)" }}>
      {tally.approve > 0 && <span style={{ color: voteColor("APPROVE") }}>{tally.approve} approve</span>}
      {tally.adjust > 0 && <span style={{ color: voteColor("ADJUST_UP") }}>{tally.adjust} adjust</span>}
      {tally.veto > 0 && <span style={{ color: voteColor("VETO") }}>{tally.veto} veto</span>}
    </span>
  );
}

export function AgentAnalysisPanel({ verdict, signalData }: {
  verdict: VerdictData;
  signalData?: { agentName: string; signals: Record<string, unknown>; confidence: number | null; reasoning: string }[];
}) {
  const [cioExpanded, setCioExpanded] = useState(false);
  const [expandedAdvisor, setExpandedAdvisor] = useState<string | null>(null);
  const stances = verdict.agentStances ?? [];
  const opinions = verdict.advisoryOpinions ?? [];
  const narrative = verdict.boardNarrative;

  // Preview: top 3 signal tags text
  const allSignals: string[] = [];
  for (const s of stances) {
    for (const sig of s.key_signals.slice(0, 2)) {
      if (!allSignals.includes(sig)) allSignals.push(sig);
    }
  }
  const previewSignals = allSignals.slice(0, 3).join(" · ");

  const boardOverrode = verdict.boardAdjustedVerdict && verdict.boardAdjustedVerdict !== verdict.recommendation;

  return (
    <CollapsiblePanel
      title="Agent Analysis"
      variant="accent"
      preview={
        <span style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", flexWrap: "wrap" }}>
          {previewSignals && <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>{previewSignals}</span>}
          <VoteTallyPreview opinions={verdict.advisoryOpinions} />
        </span>
      }
      badge={stances.length > 0 ? <Badge variant="neutral">{stances.length} agents</Badge> : undefined}
    >
      {/* Agent Consensus Panel — ring + avatars */}
      {stances.length > 0 && (
        <div style={{ marginBottom: "var(--space-md)" }}>
          <AgentConsensusPanel
            stances={stances as unknown as import("../../types/models").AgentStance[]}
            consensusScore={verdict.consensusScore}
          />
        </div>
      )}

      {/* Signal Tag Cloud */}
      {stances.length > 0 && (
        <div style={{ marginBottom: "var(--space-md)" }}>
          <SignalTagCloud
            stances={stances as unknown as import("../../types/models").AgentStance[]}
            signalData={signalData as unknown as Parameters<typeof SignalTagCloud>[0]["signalData"]}
          />
        </div>
      )}

      {/* Verdict reasoning */}
      {verdict.reasoning && (
        <div style={{
          marginBottom: "var(--space-md)",
          borderTop: "1px solid var(--glass-border)",
          paddingTop: "var(--space-md)",
        }}>
          <FormattedProse text={verdict.reasoning} />
        </div>
      )}

      {/* Advisory Board — vote bar + grid */}
      {opinions.length > 0 && (
        <div style={{ borderTop: "1px solid var(--glass-border)", paddingTop: "var(--space-md)" }}>
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "var(--space-sm)",
          }}>
            <div style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}>
              Advisory Board
            </div>
            {boardOverrode && (
              <div style={{
                fontFamily: "var(--font-mono)",
                fontWeight: 800,
                fontSize: "var(--text-sm)",
                color: verdictColor[verdict.boardAdjustedVerdict!] ?? "var(--color-accent-bright)",
              }}>
                Board: {verdictLabel[verdict.boardAdjustedVerdict!] ?? verdict.boardAdjustedVerdict}
              </div>
            )}
          </div>

          {/* Vote bar */}
          {(() => {
            const total = opinions.length || 1;
            const approve = opinions.filter(o => o.vote === "APPROVE").length;
            const adjust = opinions.filter(o => o.vote.startsWith("ADJUST")).length;
            const veto = opinions.filter(o => o.vote === "VETO").length;
            return (
              <div style={{
                height: 8,
                borderRadius: 4,
                background: "var(--color-surface-2)",
                overflow: "hidden",
                display: "flex",
                marginBottom: "var(--space-md)",
              }}>
                {approve > 0 && <div style={{ width: `${(approve / total) * 100}%`, background: "var(--color-success)" }} />}
                {adjust > 0 && <div style={{ width: `${(adjust / total) * 100}%`, background: "var(--color-accent-bright)" }} />}
                {veto > 0 && <div style={{ width: `${(veto / total) * 100}%`, background: "var(--color-error)" }} />}
              </div>
            );
          })()}

          {/* Advisor grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "var(--space-sm)" }}>
            {opinions.map((op) => {
              const vc = voteColor(op.vote);
              const isExpanded = expandedAdvisor === op.advisor_name;
              return (
                <div
                  key={op.advisor_name}
                  onClick={() => setExpandedAdvisor(isExpanded ? null : op.advisor_name)}
                  style={{
                    padding: "var(--space-md)",
                    background: "var(--color-surface-0)",
                    borderRadius: "var(--radius-sm)",
                    borderLeft: `3px solid ${vc}`,
                    display: "flex",
                    flexDirection: "column",
                    gap: "var(--space-xs)",
                    cursor: "pointer",
                    transition: "background 0.15s",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 700, fontSize: "var(--text-sm)" }}>{op.display_name}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-xs)" }}>
                      <span style={{ color: vc, fontWeight: 700, fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)" }}>
                        {voteLabel(op.vote)}
                      </span>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                        {(op.confidence * 100).toFixed(0)}%
                      </span>
                      <span style={{
                        fontSize: 9,
                        color: "var(--color-text-muted)",
                        transform: isExpanded ? "rotate(180deg)" : "none",
                        transition: "transform 0.2s",
                      }}>
                        ▼
                      </span>
                    </div>
                  </div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                    {isExpanded ? op.assessment : (op.assessment.length > 140 ? op.assessment.slice(0, 140) + "…" : op.assessment)}
                  </div>
                  {op.key_concern && (
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-error)", fontStyle: "italic" }}>
                      Risk: {isExpanded ? op.key_concern : (op.key_concern.length > 80 ? op.key_concern.slice(0, 80) + "…" : op.key_concern)}
                    </div>
                  )}
                  {op.key_endorsement && (
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-success)", fontStyle: "italic" }}>
                      Upside: {isExpanded ? op.key_endorsement : (op.key_endorsement.length > 80 ? op.key_endorsement.slice(0, 80) + "…" : op.key_endorsement)}
                    </div>
                  )}
                  <AnimatePresence>
                    {isExpanded && op.reasoning && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        style={{ overflow: "hidden" }}
                      >
                        <div style={{
                          borderTop: "1px solid var(--glass-border)",
                          paddingTop: "var(--space-sm)",
                          marginTop: "var(--space-xs)",
                        }}>
                          <FormattedProse text={op.reasoning} fontSize="var(--text-xs)" />
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* CIO Synthesis — nested expand */}
      {narrative && (narrative.narrative || narrative.risk_summary || narrative.pre_mortem) && (
        <div style={{ borderTop: "1px solid var(--glass-border)", marginTop: "var(--space-md)" }}>
          <button
            onClick={() => setCioExpanded(!cioExpanded)}
            style={{
              width: "100%",
              padding: "var(--space-sm) 0",
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              color: "var(--color-text-muted)",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              fontFamily: "var(--font-sans)",
            }}
          >
            <span>CIO SYNTHESIS</span>
            <span style={{ transform: cioExpanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▼</span>
          </button>
          <AnimatePresence>
            {cioExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                style={{ overflow: "hidden" }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)", paddingBottom: "var(--space-sm)" }}>
                  {narrative.narrative && (
                    <FormattedProse text={narrative.narrative} />
                  )}
                  {narrative.conflict_resolution && (
                    <div style={{ borderTop: "1px solid var(--glass-border)", paddingTop: "var(--space-sm)" }}>
                      <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 2 }}>Conflict Resolution</div>
                      <FormattedProse text={narrative.conflict_resolution} fontSize="var(--text-xs)" color="var(--color-text-muted)" />
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </CollapsiblePanel>
  );
}
