# Contributing to Reame

Thanks for helping. Reame is MIT-licensed and built with the same discipline
throughout — read this before opening a PR.

## How we work

- **Test first.** Every change ships with an isolated test that pins the
  *correct* expected behavior (not what the code happens to do). Dependencies
  are mocked; the unit under test is exercised directly. RED → GREEN → commit.
- **One feature, one branch, one PR.** CI must be green (Linux + macOS) before
  merge.
- **Benchmarks are measured on real hardware**, and negative results are kept
  next to the wins. Numbers you add must be reproducible from the repo.
- **Match the surrounding code** — its naming, comment density, and idiom.

## Developer Certificate of Origin

By contributing, you certify the [DCO](https://developercertificate.org/): the
contribution is your own work (or you have the right to submit it) and you
agree it is provided under the terms below. Sign your commits with `-s`:

```bash
git commit -s -m "…"
```

## Licensing of contributions

By submitting a contribution you agree that:

1. Your contribution is licensed to the project and its users under the
   **MIT License** (the project's current license), and
2. You grant **Marco Caciotti** (the project maintainer and copyright holder)
   a perpetual, irrevocable, non-exclusive, worldwide, royalty-free right to
   **relicense your contribution under any license**, including a copyleft
   (e.g. AGPL) or a commercial license, as part of a future dual-licensing of
   Reame.

This keeps the project's options open — it can stay MIT, or later offer a
commercial/enterprise edition alongside an open one — without having to track
down every past contributor for permission. Your contribution remains
available under MIT regardless of any future relicensing.

You retain the copyright to your contribution; this is a license grant, not an
assignment.

*This is a contributor agreement, not legal advice.*
