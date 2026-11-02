## Summary
- **Phase / Feature Branch:** 
- **What changed:** 

## Ownership & Contract Checklist
- [ ] Changes stay strictly within my owned directories (`AGENTS.md` §2), **or** this is an agreed shared-contract PR.
- [ ] If `contracts/**` changed, both collaborators are requested as reviewers and `mobile/src/api/generated.ts` was regenerated (`npm run codegen`).
- [ ] No new Alembic migration was generated outside System 1 (`backend/migrations/`).
- [ ] All monetary fields use integer paise (`*_paise`), not floats.
- [ ] `POST /api/v1/auth/dev-switch-role` and `<DevRoleSwitcher />` remain strictly dev-gated.

## Verification
- [ ] `cd backend && pytest -v` passes
- [ ] `cd mobile && npm run typecheck` passes

