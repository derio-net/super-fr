// Development definition: run the source guards even with an installed copy.
// opencode.json disables the global "super-fr" ID in this repo only. Distinct
// IDs are essential: OpenCode rejects duplicates BEFORE either setup can elect
// an owner. Do not replace setup with a no-op or check the filesystem for an
// installed copy: its presence does not prove active enforcement.
import plugin from "../../packages/fr-opencode-plugin/src/index";

export default { ...plugin, id: "super-fr.development" };
