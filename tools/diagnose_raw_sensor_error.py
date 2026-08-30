#!/usr/bin/env python3
"""Growstar Phase 4J – statische Diagnose für Raw-Sensor-Aufrufe.

Dieses Werkzeug verändert keine Dateien, importiert keine Growstar-Services und
sendet keine Netzwerkrequests. Es sucht nur im Python-Quelltext nach der
Fehlermeldung "Raw Sensor Werte Fehler" sowie nach Aufrufen auf einem Objekt
namens `hardware`.

Ziel: Den exakten veralteten Methodenaufruf bestimmen, bevor produktiver
Hardware-Code geändert wird.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "backups", "node_modules"}


def python_files():
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def find_raw_error_strings():
    results = []
    needles = ("Raw Sensor Werte Fehler", "Raw Sensor", "Sensor Werte Fehler")
    for path in python_files():
        text = read(path)
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(needle.lower() in line.lower() for needle in needles):
                results.append((path.relative_to(ROOT), lineno, line.strip()))
    return results


def hardware_calls():
    results = []
    for path in python_files():
        text = read(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if isinstance(func.value, ast.Name) and func.value.id == "hardware":
                results.append((path.relative_to(ROOT), node.lineno, func.attr))
    return results


def hardware_service_methods():
    candidates = [
        ROOT / "services" / "hardware.py",
        ROOT / "core" / "hardware" / "service.py",
    ]
    methods = set()
    found_files = []

    for path in candidates:
        if not path.exists():
            continue
        text = read(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        found_files.append(path.relative_to(ROOT))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "HardwareService":
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.add(child.name)

    return found_files, methods


def main():
    print("Growstar Phase 4J – Raw-Sensor-Diagnose")
    print("ROOT:", ROOT)
    print()

    matches = find_raw_error_strings()
    print("=== Fundstellen der Fehlermeldung ===")
    if matches:
        for path, line, text in matches:
            print(f"{path}:{line}: {text}")
    else:
        print("Keine passende Fehlermeldung im Python-Quelltext gefunden.")

    print()
    print("=== Aufrufe hardware.<methode>(...) ===")
    calls = hardware_calls()
    if calls:
        for path, line, method in calls:
            print(f"{path}:{line}: hardware.{method}(...)")
    else:
        print("Keine direkten Aufrufe auf einem Objekt namens 'hardware' gefunden.")

    print()
    files, methods = hardware_service_methods()
    print("=== HardwareService ===")
    if files:
        print("Definition gefunden in:", ", ".join(map(str, files)))
        print("Methoden:", ", ".join(sorted(methods)) if methods else "(keine erkannt)")
    else:
        print("Keine HardwareService-Klassendefinition in den erwarteten Dateien gefunden.")

    if methods and calls:
        missing = sorted({
            method for _, _, method in calls
            if method not in methods
        })
        print()
        print("=== Potenziell veraltete direkte Aufrufe ===")
        if missing:
            for method in missing:
                print("MÖGLICH FEHLEND:", method)
        else:
            print("Alle statisch gefundenen hardware.<methode>-Aufrufe existieren in HardwareService.")

    print()
    print("Hinweis: Dieses Skript nimmt keine Änderungen vor und führt keinen Hardware-Code aus.")


if __name__ == "__main__":
    main()
