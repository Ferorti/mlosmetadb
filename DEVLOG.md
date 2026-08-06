# DEVLOG.md

## 2026-08-04 — refactor iniciado

Refactor iniciado desde la branch `audit/full-repo-review`, con
`refactor/` como futura raíz limpia del proyecto. Empezando por la capa de
datos (`database/` + `scripts/` + `parsers/`); `api/` y `frontend/` quedan
para una fase posterior.

Ver [REFACTOR_LOG.md](REFACTOR_LOG.md) para el detalle paso a paso de qué se
copió, qué se dejó afuera, y por qué.

## 2026-08-06 — repo-root swap: `refactor/` pasa a ser la raíz real

`refactor/` deja de ser área de staging: el árbol pre-refactor se retiró a
`OLD/` y `refactor/*` se promovió a la raíz del repo. Ver Entry 16 de
[REFACTOR_LOG.md](REFACTOR_LOG.md) para el detalle (dos pases de `git mv`,
fixes de `.gitignore`, verificación de paths y corrección de docs).
