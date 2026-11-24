"""Conflict hand-backs onto the stack target (spec 2026-11-24-wave-queue-gaps R1-R6).

A queue entry ejected for a real conflict is handed back naming the commit it will be
stacked on when it re-enters (the last standing combination, else the base), re-issued
free while its head is unchanged and that commit stops leading to `main`, and held with a
carry brief when its head reaches a combination the queue built that no longer leads.
Pure: git answers ancestry in the command layer.
"""
