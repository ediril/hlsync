# Noncommercial use and paid commercial licensing

Date: 2026-10-25

## Decision

HLSync uses the unchanged PolyForm Strict License 1.0.0 with a
project-specific required copyright notice. Commercial use outside that
license's permissions requires a separate paid commercial agreement.
Emrah Diril is the licensing contact at emrah@diril.org.

## Rationale

The project charges for commercial rights while permitting free personal and
other noncommercial use. The established PolyForm license defines those
permissions, including express permissions for charitable organizations,
educational institutions, and other organizations listed in its terms.
Strict grants use for its permitted purposes but no rights to modify or
redistribute the software. The source remains readable. The standard text is
unchanged; commercial rights are offered through a separate agreement.

## Boundaries

The source remains available, but the terms restrict commercial use and are
not an open-source license. Packaging tools do not recognize a bare
`PolyForm-Strict-1.0.0` SPDX identifier, so package metadata uses
`LicenseRef-PolyForm-Strict-1.0.0` to reference the unchanged license in `LICENSE`.
This identifier does not introduce custom license terms.

Pricing, commercial-license duration, and support commitments belong in the
separate commercial agreement. PolyForm does not grant commercial rights
outside its permitted purposes or promise support. There is no runtime license
enforcement.

The already published `1.16.2` release retains its PolyForm Noncommercial terms.
Strict applies to releases distributed with the new license; it does not remove
rights already granted for earlier copies. Publish the new license in a new
version rather than reusing the prepared `1.16.2` artifacts.

## Release history

The repository starts a fresh Git history with PolyForm Strict on its first
source snapshot. An empty root commit is the baseline in `version.json`, with
the assigned counter value `1.16.2`. The next commit contains the complete source
and calculates as `1.16.3`. There are no earlier software snapshots in this
history. This preserves the version 1 release sequence without a major bump.

Version calculation advances the baseline's work-day and daily-commit values
using first-parent commit dates. Later commits on the snapshot date advance to
`1.16.4` and beyond; later work days reset the daily increment to `1`. The
baseline's starting version is fixed configuration, not a counter edited for
each release. Release artifacts preserve their computed version without Git.

The previous history and uncommitted changes are backed up separately before
replacement. They are not ancestors or refs in the new history. Rewriting Git
does not revoke any permissions already granted for previously shared copies.
