# C4 diagrams (Mermaid)

C4 views of **Clinical-GLiNER-KG** as implemented today, plus the intended outer envelope. These are Mermaid `C4Context` / `C4Container` / `C4Component` diagrams (GitHub renders them natively).

| Level | File | Question it answers |
|---|---|---|
| Context | [context.md](context.md) | Who uses it, and which external systems it talks to? |
| Container | [container.md](container.md) | What deployable pieces sit inside the system? |
| System (component) | [system.md](system.md) | How does the extraction plane actually cascade? |

Honesty rule (see [next-steps.md](../next-steps.md)): streaming, OWL/SHACL, and enterprise PHI are **intended**, not current runtime. The diagrams mark those as planned.
