# Fundamental Origin of Gravity: Evidence-First Research Audit

**Status:** OPEN / UNKNOWN — no fundamental cause established  
**Purpose:** Reproducible research ledger, not a proposed new theory  
**Branch:** `research/gravity-fundamental-origin-audit`  
**Scope:** Classical gravity, massless spin-2 consistency, thermodynamic/emergent approaches, identifiability and empirical discrimination.

## 1. Question and epistemic boundary

The target question is not merely how to reproduce Einstein's field equations. It is:

> What, if anything, explains why the observed world has a gravitational interaction with its measured universal coupling, causal structure, and low-energy dynamics?

Keep four levels separate:

1. **Phenomenology:** observations such as free fall, gravitational redshift, lensing, orbital dynamics, gravitational waves.
2. **Effective law:** a framework that predicts those observations, notably general relativity within its tested regime.
3. **Derivation:** obtaining those laws from a stated set of mathematical assumptions.
4. **Ontological/fundamental explanation:** why those assumptions and degrees of freedom obtain in nature.

Success at levels 2 or 3 is not automatically success at level 4. Equivalent effective predictions do not by themselves identify a unique microscopic ontology.

## 2. Established starting point

Einstein's field equation is

\[
G_{\mu\nu}+\Lambda g_{\mu\nu}
=\frac{8\pi G}{c^4}T_{\mu\nu}.
\]

This relates spacetime geometry to stress-energy. It does not, by itself, explain why this relation is realized or why the relevant constants and degrees of freedom exist.

The Newtonian limit gives \(a=GM/r^2\) for a test body near a spherical source, with the test body's mass cancelling under the usual inertial/gravitational mass identification. In general relativity, ideal test bodies follow geodesics of the metric, subject to the theory's assumptions and neglecting self-force and non-gravitational effects.

These are constraints a fundamental account must recover, not proof of any particular microscopic mechanism.

## 3. Route A — massless spin-2 consistency

### Primary references

- S. Weinberg (1964), *Photons and Gravitons in S-Matrix Theory: Derivation of Charge Conservation and Equality of Gravitational and Inertial Mass*, Physical Review 135, B1049. DOI: https://doi.org/10.1103/PhysRev.135.B1049
- S. Weinberg (1965), *Photons and Gravitons in Perturbation Theory: Derivation of Maxwell's and Einstein's Equations*, Physical Review 138, B988. DOI: https://doi.org/10.1103/PhysRev.138.B988
- T. Padmanabhan (2008), *From Gravitons to Gravity: Myths and Reality*, International Journal of Modern Physics D 17, 367–398. DOI: https://doi.org/10.1142/S0218271808012085; preprint https://arxiv.org/abs/gr-qc/0409089

### Conditional result

Weinberg's soft-emission/S-matrix arguments show that, under specified assumptions including Lorentz invariance, the relevant pole structure and a massless spin-2 particle, consistency imposes strong constraints on the coupling and supports equality of gravitational and inertial mass. Weinberg's 1965 perturbative construction investigates conditions under which the potentials satisfy Einstein's equations.

Do **not** compress this into an assumption-free theorem that “spin 2 proves gravity exists.” The particle's existence, masslessness, S-matrix assumptions, long-range behavior and dynamical premises are inputs. The result constrains a theory given those inputs; it does not derive why nature has a massless spin-2 excitation.

### Important qualification

Padmanabhan's analysis explicitly challenges the oversimplified claim that repeatedly coupling a linear spin-2 field to its conventional energy-momentum tensor uniquely and automatically produces the full Einstein-Hilbert theory. The precise source tensor and construction matter. Therefore any derivation must show its action, variables, gauge assumptions, coupling rule, boundary terms and convergence/closure—not merely state “self-coupling gives GR.”

## 4. Route B — thermodynamic/equation-of-state derivation

Primary reference:

- T. Jacobson (1995), *Thermodynamics of Spacetime: The Einstein Equation of State*, Physical Review Letters 75, 1260. DOI: https://doi.org/10.1103/PhysRevLett.75.1260; preprint https://arxiv.org/abs/gr-qc/9504004

Jacobson derives Einstein's equation from assumptions including entropy proportional to horizon area, the relation \(\delta Q=T\,dS\), Unruh temperature, and requiring the relation for local Rindler causal horizons through each spacetime point.

This is a real derivation of the field equation from thermodynamic premises. It is not, by itself, proof that spacetime is microscopically made of thermodynamic variables, nor does it independently derive the assumed entropy-area law or Unruh relation from a unique microscopic theory.

**Audit requirement:** list every premise and classify it as independently supported, derived elsewhere, stipulated, or unresolved.

## 5. Route C — induced/emergent gravity

Primary starting point:

- A. D. Sakharov (1967), *Vacuum Quantum Fluctuations in Curved Space and the Theory of Gravitation*, Doklady Akademii Nauk SSSR 177, 70–71. Bibliographic record: https://www.mathnet.ru/eng/dan33444

Induced-gravity ideas investigate whether effective gravitational dynamics can arise from quantum fields or more microscopic degrees of freedom. Such proposals must specify the underlying theory, regularization/cutoff, induced terms, constants, stability, and why the observed low-energy limit follows.

A derivation of an Einstein-Hilbert term in an effective action does not alone explain the measured value of Newton's constant, the small observed cosmological constant, or why the assumed microscopic theory is physically realized.

Do not treat “emergent” as an explanation unless the microphysical degrees of freedom and derivation are explicit.

## 6. What the routes establish—and do not

| Claim | Status | Reason |
|---|---|---|
| GR is a highly successful low-energy/classical description in its tested domain | ESTABLISHED within tested regimes | Empirical success; not a complete quantum/fundamental theory |
| Consistency constrains massless spin-2 couplings | ESTABLISHED conditionally | Follows from stated S-matrix/field-theory assumptions |
| Einstein dynamics can be obtained from suitable spin-2 constructions | ESTABLISHED for specified constructions | The derivation is assumption- and procedure-dependent |
| Einstein dynamics can follow from thermodynamic horizon premises | ESTABLISHED for Jacobson's setup | Premises do not thereby receive a unique microscopic explanation |
| Gravity is definitely fundamental | NOT ESTABLISHED |
| Gravity is definitely emergent | NOT ESTABLISHED |
| A unique fundamental cause has been identified | UNKNOWN / NOT ESTABLISHED |
| Equal effective predictions imply equal ontology | FALSE in general | Effective theories can underdetermine microscopic realizations |

## 7. Research protocol for a genuine fundamental result

For each candidate model, create a ledger with:

- exact primary source and version;
- explicit assumptions and domains of validity;
- fundamental variables and degrees of freedom;
- action or equations of motion;
- derivation steps, including boundary terms and gauge constraints;
- recovered observables and approximation order;
- parameter map and dimensional checks;
- known counterexamples, no-go results and instability checks;
- independent derivation or calculation;
- a discriminator against competing models;
- status: KNOWN/CLOSED, APPROXIMATION, UNKNOWN, REFUTED, or POTENTIAL NOVEL RESULT.

A novelty claim is blocked until the result is checked against the primary literature and the relevant reference frameworks, including CODATA/PDG where constants or particle properties are involved and Planck/DESI where cosmological observables are involved. A citation count or abstract alone is not a novelty audit.

## 8. The decisive next task

Do not invent another speculative substrate yet. First formalize the common low-energy target and determine which assumptions are shared by the spin-2 and thermodynamic routes.

1. Derive the soft spin-2 universality constraint from the primary source, stating the exact S-matrix assumptions.
2. Independently reconstruct Jacobson's thermodynamic derivation and list its premises.
3. Compare the assumptions, not just the final Einstein equation.
4. Search for a measurable regime in which explicit candidate models disagree.
5. If no discriminator follows, record underdetermination rather than choose a favorite ontology.

A fundamental explanation would need either (a) derive the shared assumptions from a deeper theory, or (b) produce a discriminating, testable prediction. Rephrasing GR or obtaining its equations from another set of premises is not sufficient.

## 9. Repository/workflow note

The AuthorityLab README and architecture explicitly distinguish structural completeness from factual truth and state that a validator's PASS is not source authentication or independent proof. This research record follows that boundary: literature retrieval is evidence of what a source says, not proof that its claim is correct. A future implementation could represent each premise, derivation step, source, counterexample and verification status as typed evidence, but the framework itself cannot decide the physics without domain-specific derivations and independent review.

## 10. Correction log

An earlier conversational citation associated Padmanabhan's *From Gravitons to Gravity: Myths and Reality* with DOI 10.1103/PhysRevD.109.044014. That association is incorrect. The verified bibliographic DOI for Padmanabhan's paper is 10.1142/S0218271808012085 (2008), with preprint arXiv:gr-qc/0409089. The DOI 10.1103/PhysRevD.109.044014 belongs to a different 2024 paper, *Emergent modified gravity: The perfect fluid and gravitational collapse*, by Erick I. Duque. This correction is retained so downstream work does not propagate the citation error.

## Current decision

**UNKNOWN — fundamental cause not identified.**  
**PASS — research scope and epistemic boundary defined.**  
**NEXT — reconstruct and compare the two derivations from primary sources before proposing a new mechanism.**
