#!/usr/bin/env python3
"""Build Kotlin stand-ins for the Bitwarden SDK types the GPL Android app constructs.

The shapes come from call sites in the pinned bitwarden/android tree (GPL-3.0).
The file does not read the SDK binary or sdk-internal.
"""
import os
import re
import pathlib
import collections

ANDROID = pathlib.Path(os.environ.get("BW_ANDROID", "/tmp/bw-android"))
OUT = pathlib.Path(__file__).resolve().parent / "komboe-sdk" / "src" / "main" / "kotlin"

SDK_PREFIXES = (
    "com.bitwarden.vault.",
    "com.bitwarden.sdk.",
    "com.bitwarden.crypto.",
    "com.bitwarden.send.",
    "com.bitwarden.fido.",
    "com.bitwarden.generators.",
    "com.bitwarden.policies.",
    "com.bitwarden.collections.",
    "com.bitwarden.exporters.",
    "com.bitwarden.auth.",
    "com.bitwarden.organizations.",
    "com.bitwarden.servercommunicationconfig.",
)

# com.bitwarden.core is the SDK, except these packages which live in the Android tree.
CORE_SKIP = ("com.bitwarden.core.data.", "com.bitwarden.core.util.", "com.bitwarden.core.di.")


def is_sdk(imp: str) -> bool:
    if imp.startswith("com.bitwarden.core."):
        return not imp.startswith(CORE_SKIP)
    return imp.startswith(SDK_PREFIXES)


def kotlin_files():
    for root, dirs, files in os.walk(ANDROID):
        if any(part in root for part in ("/build/", "/src/test", "/src/androidTest", "/.git")):
            continue
        if "/src/main/" not in root and "/src/fdroid/" not in root and "/src/debug/" not in root:
            continue
        for name in files:
            if name.endswith(".kt"):
                yield pathlib.Path(root) / name


def files_with_imports():
    imports = {}
    parsed = []
    for path in kotlin_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        local = {}
        for imp in re.findall(r"^import (com\.bitwarden\.[A-Za-z0-9_.]+)", text, re.M):
            if is_sdk(imp):
                simple = imp.split(".")[-1]
                local[simple] = imp.rsplit(".", 1)[0]
                imports.setdefault(simple, imp.rsplit(".", 1)[0])
        if local:
            parsed.append((text, local))
    return parsed, imports


def scan_args(text, open_paren):
    """Return the argument source inside the paren that starts at open_paren."""
    i = open_paren + 1
    depth = 1
    start = i
    parts = []
    buf = []
    in_str = None
    while i < len(text) and depth:
        c = text[i]
        if in_str:
            buf.append(c)
            if c == "\\" and i + 1 < len(text):
                buf.append(text[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ('"', "'"):
            in_str = c
            buf.append(c)
            i += 1
            continue
        if c in "({[":
            depth += 1
            buf.append(c)
        elif c in ")}]":
            depth -= 1
            if depth == 0:
                parts.append("".join(buf).strip())
                break
            buf.append(c)
        elif c == "," and depth == 1:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    named = []
    for part in parts:
        if not part:
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([\s\S]+)$", part)
        if m:
            named.append((m.group(1), m.group(2).strip()))
        else:
            named.append((None, part.strip()))
    return named


def infer(expr, known):
    e = expr.strip()
    if e == "null":
        return None, True
    if e in ("true", "false"):
        return "Boolean", False
    if re.fullmatch(r"-?\d+", e):
        return "Int", False
    if e.endswith(".toUInt()") or ".toUInt()" in e and e.endswith(")"):
        if e.endswith(".toUInt()"):
            return "UInt", False
    if e.endswith(".toUByte()"):
        return "UByte", False
    if e.endswith(".toULong()"):
        return "ULong", False
    if e.startswith('"') or e.startswith("\"\"\""):
        return "String", False
    if e.startswith("emptyList") or e.startswith("listOf") or e.startswith("mutableListOf"):
        return "List<Any?>", False
    if e.startswith("emptyMap") or e.startswith("mapOf"):
        return "Map<String, Any?>", False
    if e.endswith(".orEmpty()") and ("List" in e or "list" in e or "collections" in e):
        return "List<Any?>", False
    if ".instant()" in e or e == "Instant.EPOCH":
        return "java.time.Instant", False
    m = re.match(r"^([A-Z][A-Za-z0-9_]*)\(", e)
    if m and m.group(1) in known:
        return m.group(1), False
    m = re.match(r"^([A-Z][A-Za-z0-9_]*)\.([A-Za-z0-9_]+)", e)
    if m and m.group(1) in known:
        return m.group(1), False
    if e.endswith(".toByteArray()"):
        return "ByteArray", False
    return "Any?", "null" in e


def merge_type(old, new):
    if old is None:
        return new
    if new is None:
        return (old[0], True) if old[0] else old
    name_o, null_o = old
    name_n, null_n = new
    if name_o is None:
        return (name_n, True)
    if name_n is None:
        return (name_o, True)
    if name_o == name_n:
        return (name_o, null_o or null_n)
    if name_o == "Any?":
        return (name_n, null_o or null_n)
    if name_n == "Any?":
        return (name_o, null_o or null_n)
    # Prefer a concrete SDK type over Any.
    return (name_o, null_o or null_n)


def default_for(type_name, nullable):
    if nullable or type_name in (None, "Any?"):
        return "null"
    if type_name == "Boolean":
        return "false"
    if type_name == "Int":
        return "0"
    if type_name == "UInt":
        return "0u"
    if type_name == "UByte":
        return "0u"
    if type_name == "ULong":
        return "0uL"
    if type_name == "String":
        return '""'
    if type_name.startswith("List"):
        return "emptyList()"
    if type_name.startswith("Map"):
        return "emptyMap()"
    if type_name == "ByteArray":
        return "byteArrayOf()"
    if type_name == "java.time.Instant":
        return "java.time.Instant.EPOCH"
    return None


def strip_comments(text):
    out = []
    i = 0
    n = len(text)
    in_str = None
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if text.startswith('"""', i):
            end = text.find('"""', i + 3)
            end = n if end < 0 else end + 3
            out.append(text[i:end])
            i = end
            continue
        if c in "\"'":
            in_str = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            nxt = text.find("\n", i)
            i = n if nxt < 0 else nxt
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            nxt = text.find("*/", i + 2)
            i = n if nxt < 0 else nxt + 2
            out.append(" ")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def member_ok(text, index, member):
    if not member[:1].isupper():
        return False
    prefix = text[max(0, index - 12):index]
    if re.search(r"\bfun\s+$", prefix):
        return False
    return True


def main():
    parsed, imports = files_with_imports()
    known = set(imports)
    ctors = collections.defaultdict(list)
    variants = collections.defaultdict(lambda: collections.defaultdict(list))
    enumish = collections.defaultdict(set)

    for raw, local in parsed:
        text = strip_comments(raw)
        for m in re.finditer(r"(?<!\.)\b([A-Z][A-Za-z0-9_]*)\s*\(", text):
            name = m.group(1)
            if name not in local:
                continue
            ctors[name].append(scan_args(text, m.end() - 1))

        for m in re.finditer(r"(?<!\.)\b([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)", text):
            outer, member = m.group(1), m.group(2)
            if outer not in local or not member_ok(text, m.start(), member):
                continue
            rest = text[m.end():m.end() + 1]
            if rest == "(":
                variants[outer][member].append(scan_args(text, m.end()))
            elif member.isupper() or "_" in member:
                enumish[outer].add(member)

        for m in re.finditer(r"\bis\s+(?<!\.)([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)", text):
            outer, member = m.group(1), m.group(2)
            if outer in local and member[:1].isupper():
                variants[outer].setdefault(member, [])

    # A type is sealed when it has named members that are constructed or used in `is`.
    sealed = {}
    enums = {}
    for outer, members in variants.items():
        if members:
            sealed[outer] = members
    for outer, consts in enumish.items():
        if outer in sealed:
            for const in consts:
                sealed[outer].setdefault(const, [])
            continue
        # Pure constants. Ignore lowercase method-like names that are only accessed.
        screaming = {c for c in consts if c.isupper() or "_" in c}
        if screaming and len(screaming) == len(consts):
            enums[outer] = screaming
        elif screaming and not ctors.get(outer):
            enums[outer] = screaming

    # Data classes are types that are constructed and are not sealed.
    data = {}
    for name, calls in ctors.items():
        if name in sealed or name in enums:
            continue
        fields = collections.OrderedDict()
        omitted = collections.Counter()
        present = collections.Counter()
        calls_named = 0
        for args in calls:
            if any(n is None for n, _ in args):
                continue
            calls_named += 1
            seen = set()
            for n, expr in args:
                seen.add(n)
                present[n] += 1
                typ, nullable = infer(expr, known)
                fields[n] = merge_type(fields.get(n), (typ, nullable))
            # omitted tracking filled after we know the full field set
        if calls_named == 0 or not fields:
            continue
        for args in calls:
            if any(n is None for n, _ in args):
                continue
            seen = {n for n, _ in args}
            for n in fields:
                if n not in seen:
                    omitted[n] += 1
        data[name] = (fields, omitted, calls_named)

    # Interfaces: implemented by the app, never constructed as a data class we already have.
    impl = collections.defaultdict(list)
    for m in re.finditer(r"\)\s*:\s*([A-Za-z0-9_]+)\s*(?:\{|,)", text):
        name = m.group(1)
        if name in known:
            impl[name].append(m.start())
    # Also `class Foo(...) : Bar`.
    for m in re.finditer(r":\s*([A-Z][A-Za-z0-9_]+)\s*[,{]", text):
        name = m.group(1)
        if name in known and name not in data and name not in sealed and name not in enums:
            impl[name].append(m.start())

    # Pull override signatures that appear near an implementor. Simpler: collect every
    # `override ... fun` whose surrounding class header mentions the interface. Too fuzzy.
    # Hand-written client covers behavior; generated interfaces below use the override
    # functions we can see in files that import the interface.

    packages = collections.defaultdict(list)
    rendered = set()

    def emit(pkg, source):
        packages[pkg].append(source)

    for name, consts in sorted(enums.items()):
        pkg = imports[name]
        body = "\n".join(f"    {c}," for c in sorted(consts))
        emit(pkg, f"enum class {name} {{\n{body}\n}}")
        rendered.add(name)

    for name, members in sorted(sealed.items()):
        pkg = imports[name]
        parts = []
        for member, calls in sorted(members.items()):
            if not calls or all(not args for args in calls):
                if any(args for args in calls):
                    pass
                # object when no named fields were parsed
                fields = collections.OrderedDict()
                for args in calls:
                    for n, expr in args:
                        if n is None:
                            continue
                        fields[n] = merge_type(fields.get(n), infer(expr, known))
                if not fields:
                    parts.append(f"    object {member} : {name}()")
                    continue
            else:
                fields = collections.OrderedDict()
                for args in calls:
                    for n, expr in args:
                        if n is None:
                            continue
                        fields[n] = merge_type(fields.get(n), infer(expr, known))
            params = []
            for fname, (typ, nullable) in fields.items():
                shown = typ or "Any?"
                if nullable and not shown.endswith("?"):
                    shown += "?"
                default = default_for(typ, nullable or shown.endswith("?"))
                piece = f"val {fname}: {shown}"
                if default is not None:
                    piece += f" = {default}"
                params.append(piece)
            if params:
                parts.append(f"    data class {member}(\n        " + ",\n        ".join(params) + f"\n    ) : {name}()")
            else:
                parts.append(f"    object {member} : {name}()")
        emit(pkg, f"sealed class {name} {{\n" + "\n".join(parts) + "\n}")
        rendered.add(name)

    for name, (fields, omitted, calls_named) in sorted(data.items()):
        pkg = imports[name]
        params = []
        for fname, (typ, nullable) in fields.items():
            shown = typ or "Any?"
            if nullable and not shown.endswith("?"):
                shown += "?"
            needs_default = omitted[fname] > 0 or nullable or shown.endswith("?")
            piece = f"val {safe(fname)}: {shown}"
            if needs_default:
                default = default_for(typ, nullable or shown.endswith("?"))
                if default is None:
                    default = "null"
                    if not shown.endswith("?"):
                        shown += "?"
                        piece = f"val {safe(fname)}: {shown}"
                piece += f" = {default}"
            params.append(piece)
        if not params:
            emit(pkg, f"class {name}")
        else:
            emit(pkg, "data class " + name + "(\n    " + ",\n    ".join(params) + "\n)")
        rendered.add(name)

    # Leftover imported types become empty classes so references resolve; the compiler
    # then tells us which members are missing.
    for name, pkg in sorted(imports.items()):
        if name in rendered:
            continue
        if name in ("initLogger",):
            continue
        emit(pkg, f"open class {name}")

    header = (
        "// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.\n"
        "// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.\n"
    )
    for pkg, chunks in packages.items():
        path = OUT.joinpath(*pkg.split("."), "Models.kt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header + f"package {pkg}\n\n" + "\n\n".join(chunks) + "\n", encoding="utf-8")
        print(f"{path.relative_to(OUT)}  {len(chunks)} types")
    postprocess()


def postprocess():
    """Adjust a few shapes the call-site scan cannot see, then drop types we implement by hand."""
    def sub(path, old, new):
        file = OUT / path
        text = file.read_text()
        if old not in text:
            raise SystemExit(f"missing snippet in {path}: {old[:80]!r}")
        file.write_text(text.replace(old, new, 1))

    sub(
        "com/bitwarden/crypto/Models.kt",
        "open class EncString\n\nopen class PasswordProtectedKeyEnvelope\n",
        "typealias EncString = String\n\ntypealias PasswordProtectedKeyEnvelope = String\n",
    )
    sub(
        "com/bitwarden/core/Models.kt",
        "sealed class DeriveKeyConnectorException {",
        "sealed class DeriveKeyConnectorException(message: String = \"derive key connector\") : Exception(message) {",
    )
    sub(
        "com/bitwarden/core/Models.kt",
        "sealed class EncryptionSettingsException {",
        "sealed class EncryptionSettingsException(message: String = \"encryption settings\") : Exception(message) {",
    )
    sub(
        "com/bitwarden/vault/Models.kt",
        "sealed class TotpException {",
        "sealed class TotpException(message: String = \"totp\") : Exception(message) {",
    )
    sub(
        "com/bitwarden/vault/Models.kt",
        "data class DecryptCipherListResult(\n    val successes: List<Any?>,\n    val failures: List<Any?>\n)",
        "data class DecryptCipherListResult(\n    val successes: List<CipherListView> = emptyList(),\n    val failures: List<Cipher> = emptyList()\n)",
    )
    sub(
        "com/bitwarden/vault/Models.kt",
        "open class AttachmentEncryptResult\n\nopen class EncryptionContext\n\nopen class Fido2CredentialNewView\n\nopen class Fido2CredentialView\n\nopen class TotpResponse\n",
        """data class AttachmentEncryptResult(val attachment: Attachment)
data class EncryptionContext(
    val cipher: Cipher,
    val encryptedFor: String,
    val encryptedByKeyId: String? = null,
)
open class Fido2CredentialNewView
open class Fido2CredentialView
data class TotpResponse(val code: String, val period: UInt)
""",
    )
    sub(
        "com/bitwarden/exporters/Models.kt",
        """sealed class ExportFormat {
    object EncryptedJson : ExportFormat()
}""",
        """sealed class ExportFormat {
    object Json : ExportFormat()
    object Csv : ExportFormat()
    data class EncryptedJson(val password: String) : ExportFormat()
}""",
    )
    sub(
        "com/bitwarden/generators/Models.kt",
        "open class AppendType\n",
        "enum class AppendType { Random, Website }\n",
    )
    sdk_path = OUT / "com/bitwarden/sdk/Models.kt"
    skip_open = {
        "open class AuthClient",
        "open class CipherRepository",
        "open class CipherViewWrapper",
        "open class Fido2CredentialStore",
        "open class Fido2UserInterface",
        "open class FolderRepository",
        "open class GeneratorClients",
        "open class LocalUserDataKeyStateRepository",
        "open class LogCallback",
        "open class ServerCommunicationConfigRepository",
        "open class VaultClient",
    }
    kept = []
    lines = sdk_path.read_text().splitlines(True)
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("data class Client("):
            while i < len(lines) and lines[i].strip() != ")":
                i += 1
            i += 1
            continue
        if stripped.startswith("sealed class BitwardenException"):
            while i < len(lines) and lines[i].strip() != "}":
                i += 1
            i += 1
            continue
        if stripped in skip_open:
            i += 1
            continue
        kept.append(lines[i])
        i += 1
    sdk_path.write_text("".join(kept))
    core = (OUT / "com/bitwarden/core/Models.kt").read_text()
    for piece in (
        "open class ClientManagedTokens\n\n",
        "open class StateBridgeForeignImpl\n\n",
        "open class RegisterKeyResponse\n\n",
        "open class KeyConnectorResponse\n\n",
        "open class EnrollPinResponse\n\n",
        "open class UpdateKdfResponse\n\n",
        "open class UpdatePasswordResponse\n\n",
    ):
        core = core.replace(piece, "")
    (OUT / "com/bitwarden/core/Models.kt").write_text(core)


def safe(name):
    if name in {"public", "private", "object", "when", "in", "is", "val", "var", "fun", "class"}:
        return f"`{name}`"
    return name


if __name__ == "__main__":
    main()
