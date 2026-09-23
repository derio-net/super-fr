# Uninstall installed rules plan

First make the fake-home integration test expose the current leak by deriving
the installed filenames from install.sh and checking that install followed by
uninstall leaves none of those files behind. Then give installation and
uninstallation one authoritative filename list, preserving cleanup of the
retired rule, and link the regression test to the existing conventions
acceptance row. Finish with the focused installer tests and acceptance check.
