# SECURITY POLICY & AUDIT REPORT

## 1. Zero-Exposure Credential Architecture
- **No Secret Printing:** API keys and HMAC secrets are loaded strictly into memory and never logged, returned via REST endpoints, or rendered in frontend templates.
- **Header Verification:** Authentication headers (`api-key`, `signature`, `timestamp`) are created dynamically inside backend requests and discarded immediately after HTTP execution.
- **Git & Package Safety:** `.gitignore` excludes `.env`, `*.db`, and sensitive log files.

## 2. Deterministic Execution Protection
- **Decoupled Execution Gate:** The Trader Agent is strictly isolated from arbitrary AI prompts. All trades must satisfy mathematical boundary conditions.
- **Skeptic Veto:** The Skeptic Agent holds unilateral authority to reject trades with illiquidity, adverse funding rates ($>0.15\%$), or parabolic extensions ($>50\%$).
- **Risk Engine Override:** The Risk Engine sits outside the committee and terminates order submission if daily loss exceeds $3\%$, max positions $\ge 1$, or margin exceeds equity.

## 3. Network & Connection Hardening
- **HMAC-SHA256 Signatures:** Prevents replay attacks via UNIX timestamps with 5-second validity windows.
- **Idempotency Protection:** Pre-order verification prevents duplicate orders and enforces strict anti-martingale / no-averaging-down rules.
