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


---

## 11. Technical reconstruction: what the two derivations actually force

This section makes the logical steps explicit. Units are set to \(c=\hbar=k_B=1\) where stated. It is a reconstruction of known arguments, not a new theorem.

### 11.1 Soft massless spin-2 emission: the conditional universality result

For a scattering process with hard external momenta \(p_i^\mu\), add one graviton of momentum \(q^\mu\) in the soft limit \(q\to0\). The leading pole factor has the form

\[
\mathcal M_{n+1}(q,\varepsilon)\simeq
\left[\sum_i \eta_i g_i
\frac{p_i^\mu p_i^\nu\varepsilon_{\mu\nu}}{p_i\!\cdot q}\right]
\mathcal M_n ,
\]

up to normalization conventions. Here \(\eta_i=+1\) for outgoing and \(-1\) for incoming legs; \(g_i\) denotes the coupling for the relevant external species, and \(\varepsilon_{\mu\nu}\) is the graviton polarization. The pole structure assumes a massless spin-2 state and the usual factorization/S-matrix conditions; it is not a derivation of that state's existence.

A massless spin-2 polarization has a gauge redundancy. At leading order, shift

\[
\varepsilon_{\mu\nu}\mapsto
\varepsilon_{\mu\nu}+q_\mu\xi_\nu+q_\nu\xi_\mu .
\]

The change in the bracket is proportional to

\[
\xi_\nu\sum_i \eta_i g_i p_i^\nu .
\]

For the amplitude to be gauge invariant for arbitrary allowed \(\xi_\nu\), consistency requires

\[
\boxed{\sum_i \eta_i g_i p_i^\nu=0.}
\]

Energy-momentum conservation gives \(\sum_i\eta_i p_i^\nu=0\). In generic interacting processes involving different species, the stronger weighted condition is compatible with arbitrary conserved momenta only when the relevant couplings are universal (or when additional special restrictions/symmetries make the weighted sum vanish). This is the core logic behind the universality constraint; it is not a proof without assumptions that every conceivable model must contain a graviton.

**What follows:** if a Lorentz-invariant S-matrix description contains a long-range massless spin-2 particle with the assumed factorization and gauge redundancy, consistent coupling is highly constrained and universal coupling follows under generic-process assumptions.

**What does not follow:** why the massless spin-2 state exists; why the universe has the assumed S-matrix/Lorentz structure; why its coupling has the measured value; or why the quantum theory has a particular vacuum. Those are upstream questions.

**Reference basis:** Weinberg, *Phys. Rev.* 135, B1049 (1964), DOI 10.1103/PhysRev.135.B1049; Weinberg, *Phys. Rev.* 138, B988 (1965), DOI 10.1103/PhysRev.138.B988. The later soft-theorem formulation and its relation to conservation laws are discussed by Cachazo and Strominger, arXiv:1404.4091. This section is a derivation sketch; a publication-grade proof must compare conventions and hypotheses against the full primary texts.

### 11.2 Jacobson's thermodynamic route: reconstruction of the local argument

Assume local Lorentzian spacetime structure, local Rindler causal horizons, entropy proportional to horizon area, and the Clausius relation \(\delta Q=T\,\delta S\) for every such horizon. In units \(c=\hbar=k_B=1\), write

\[
\delta S=\alpha\,\delta A,\qquad T=\frac{\kappa}{2\pi},
\]

where \(\alpha\) is the entropy-per-area coefficient and \(\kappa\) is the local boost acceleration/surface-gravity normalization. The local boost-energy flux through a horizon patch is

\[
\delta Q=\int T_{\mu\nu}\,\chi^\mu\,d\Sigma^\nu ,
\]

with \(T_{\mu\nu}\) the matter stress-energy tensor and \(\chi^\mu\) the approximate local boost Killing field. Near the local horizon, parameterized by affine parameter \(\lambda\), \(\chi^\mu\) is proportional to \(-\kappa\lambda k^\mu\), where \(k^\mu\) is the horizon generator.

The area change is controlled by the expansion \(\theta\). The Raychaudhuri equation is

\[
\frac{d\theta}{d\lambda}
=-\frac{1}{2}\theta^2-\sigma_{\mu\nu}\sigma^{\mu\nu}
-R_{\mu\nu}k^\mu k^\nu
\]

for hypersurface-orthogonal null generators in four dimensions. At a chosen local-equilibrium point, set \(\theta=0\); to first order in the small horizon patch, the quadratic terms do not contribute to the leading area variation. Thus the leading area change is proportional to the integral of \(-\lambda R_{\mu\nu}k^\mu k^\nu\). Equating \(\delta Q=T\delta S\) for all local null directions yields

\[
R_{\mu\nu}k^\mu k^\nu
=\frac{2\pi}{\alpha}\,T_{\mu\nu}k^\mu k^\nu
\]

for every null vector \(k^\mu\), with the coefficient depending on the normalization convention for \(\alpha\). Since a symmetric tensor whose contraction with every null vector vanishes must be proportional to the metric, this implies

\[
R_{\mu\nu}+\Phi g_{\mu\nu}
=\frac{2\pi}{\alpha}T_{\mu\nu}.
\]

Using stress-energy conservation and the contracted Bianchi identity fixes the position dependence of \(\Phi\) and gives the Einstein equation with a cosmological-constant integration term. With \(\alpha=1/(4G)\) in these units, the coefficient is \(8\pi G\).

**Premises that are not derived by this argument itself:** (i) a spacetime/local causal-horizon structure on which local Rindler horizons can be defined; (ii) area-proportional entropy and its coefficient; (iii) the Unruh temperature relation; (iv) local equilibrium and the Clausius relation for every local horizon; (v) the matter stress tensor and its conservation. The derivation shows that Einstein dynamics follows if these premises hold. It does not independently identify the microscopic degrees of freedom that carry the entropy or derive the entropy-area coefficient from a unique fundamental theory.

**Primary source:** T. Jacobson, *Phys. Rev. Lett.* 75, 1260 (1995), DOI 10.1103/PhysRevLett.75.1260; arXiv:gr-qc/9504004. The exact numerical factors depend on unit and entropy conventions; the structural inference above is the target of this reconstruction.

### 11.3 The overlap is narrower than “both prove emergence”

| Feature | Soft spin-2 route | Jacobson thermodynamic route |
|---|---|---|
| Starting structure | Lorentz-invariant scattering amplitudes; massless spin-2 pole and gauge redundancy | Local spacetime causal structure; local Rindler horizons |
| Key consistency condition | Gauge invariance of soft emission amplitude | Clausius relation plus area variation/Raychaudhuri equation |
| Universality source | Gauge consistency and momentum conservation, under generic-process assumptions | Universal local horizon thermodynamics and the same matter stress tensor |
| What is derived | Strong constraints on coupling; specified constructions can yield Einstein-like dynamics | Einstein equation as an equation of state from thermodynamic premises |
| Upstream unknown | Why the massless spin-2 state and S-matrix assumptions obtain | Microscopic origin of entropy-area law, horizon thermodynamics, and spacetime structure |
| Direct discriminant supplied by the derivation alone? | No | No |

The shared output is a constrained low-energy gravitational description. The routes do **not** share an identical premise set: one is an amplitude/gauge-consistency argument, the other a local horizon thermodynamic argument. Their common Einstein-like output does not prove their assumptions are equivalent or that either ontology is correct.

### 11.4 Identifiability test: same effective observables do not identify the substrate

Let the measured low-energy observable vector be \(O\), and let \(\theta\) denote microscopic parameters of a candidate completion. If two distinct completions \(\theta_1\ne\theta_2\) satisfy

\[
O(\theta_1)=O(\theta_2)
\]

through the precision and energy range currently tested, then those observations do not identify which completion is realized. Locally, identifiability can be studied with \(J=\partial O/\partial\theta\); directions in parameter space not changing \(O\) to the measured order remain unconstrained. A full rank for a chosen finite parameterization would only establish local identifiability within that parameterization—not prove the parameterization exhausts nature's possibilities.

This is a logical underdetermination statement, not evidence that the completions are equally plausible. Priors or aesthetic preferences cannot substitute for a measured discriminator.

### 11.5 Candidate empirical discriminators (not claimed discoveries)

The useful search target is not “a test of emergence” in general; it is a pair of explicit models that make different quantitative predictions for the same observable under the same conditions.

1. **Equivalence principle / composition dependence:** compare predicted free-fall accelerations for different materials or internal energy states. A nonzero differential acceleration would constrain universal metric coupling, but does not uniquely select an emergent theory. Null results bound violations rather than prove exact universality.
2. **Gravitational-wave propagation and extra polarizations:** compare dispersion, speed, polarization content, and amplitude damping against GR. A deviation can rule out model regions; it does not by itself identify the microscopic origin.
3. **Strong-field dynamics:** compare waveform predictions, compact-object structure, and post-merger behavior for explicit theories, including stability and parameter degeneracies.
4. **Quantum-source tests:** specify whether a model predicts nonclassical gravitational mediation, measurement-induced disturbance, decoherence, or a definite departure from a classical-field model. Proposals are not evidence of a detected effect; model-independent interpretation requires care.
5. **Cosmology:** compare expansion and structure-growth observables only after controlling degeneracies with matter content, initial conditions, calibration, and nuisance parameters. A fit improvement is not an ontology proof.

The 2020 review by Tino et al. surveys precision tests of gravity and the equivalence principle; the Particle Data Group's 2024 review *Experimental Tests of Gravitational Theory* provides an authoritative baseline for established constraints. These are constraint frameworks, not evidence for a unique microscopic cause. The 2024 proposal by Bose et al. and collaborators on testing whether gravity acts as a quantum entity is a proposed discriminator, not a completed detection.

### 11.6 Updated decision and work status

- **PASS (mathematical structure, conditional):** the leading soft spin-2 gauge variation yields a weighted momentum-conservation constraint; Jacobson's local-horizon argument maps its premises to Einstein dynamics.
- **PARTIAL:** the arguments have been reconstructed at outline level, but the full original papers have not been independently line-by-line verified in this work session.
- **UNKNOWN:** whether either premise set is fundamental; whether gravity is ontologically fundamental or emergent; the microscopic origin of the measured coupling and cosmological constant.
- **NOT CLAIMED:** a new theory, new derivation, confirmed quantum gravity, or a novel empirical prediction.
- **Next hard gate:** choose explicit competing microscopic models, derive the same observable in both, check dimensions/limits/stability, and show a quantitative difference that survives nuisance-parameter degeneracies and existing bounds. Without this, there is no defensible route from the current evidence to a unique “fundamental cause.”

### References added for this reconstruction

- Weinberg, S. (1964), “Photons and Gravitons in S-Matrix Theory,” *Physical Review* 135, B1049. https://doi.org/10.1103/PhysRev.135.B1049
- Weinberg, S. (1965), “Photons and Gravitons in Perturbation Theory,” *Physical Review* 138, B988. https://doi.org/10.1103/PhysRev.138.B988
- Jacobson, T. (1995), “Thermodynamics of Spacetime: The Einstein Equation of State,” *Physical Review Letters* 75, 1260. https://doi.org/10.1103/PhysRevLett.75.1260
- Cachazo, F. & Strominger, A. (2014), “Evidence for a New Soft Graviton Theorem,” arXiv:1404.4091. https://arxiv.org/abs/1404.4091
- Tino, G. M. et al. (2020), “Precision Gravity Tests and the Einstein Equivalence Principle,” *Progress in Particle and Nuclear Physics* 112, 103772. https://doi.org/10.1016/j.ppnp.2020.103772
- Particle Data Group, “Experimental Tests of Gravitational Theory,” Review of Particle Physics 2024. https://pdg.lbl.gov/2025/reviews/rpp2024-rev-gravity-tests.pdf
- Bose, S. et al. (2024), “Testing Whether Gravity Acts as a Quantum Entity When Measured,” *Physical Review Letters* 133, 180201. https://doi.org/10.1103/PhysRevLett.133.180201
