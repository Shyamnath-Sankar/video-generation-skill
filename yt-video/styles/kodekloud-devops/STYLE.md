# kodekloud-devops: friendly DevOps/cloud cartoon (KodeKloud-inspired)

Bright, approachable, a little playful: infrastructure explained as toy-like objects you can see move. Working demo: `demo/` (what is a Kubernetes Pod), builds as a Short (stacked) and as 16:9 (pod left, nodes right).

## Look
- **Background**: soft sky gradient `#EAF2FF → #CFE2FF` with a few soft cloud blobs (`background.kind: sky`).
- **Objects**: flat white cards with **5 px navy outlines** (`#12224A`), chunky radius 22–28 px, a **hard offset shadow** (`8px 8px 0 navy`). Containers, servers, nodes, databases, queues as labelled boxes/cylinders with simple line icons (Lucide-style, one stroke weight).
- **Colours**: primary blue `#2563EB`, orange `#FF8A00`, green `#16A34A` (healthy/success), yellow `#FACC15` (tags/labels), red `#DC2626` only for failures. Pods/groups: dashed outline with a pale blue fill `#DBEAFE`.
- **Terminal**: dark slate card `#0F172A` with traffic-light dots, JetBrains Mono 30–36 px, green `$` prompt, blinking caret.
- **Type**: Nunito 900 for labels and captions, JetBrains Mono for commands, IPs, YAML.
- **Captions**: `pop`, dark navy text with a white outline, active word blue.

## Motion
- Springy pops with overshoot are welcome (`[16, 0.62]`): things *boing* into place.
- Objects persist and move: a pod *flies* into a node, a container *slides* into a pod, a failing pod turns red, gets an X and drops away, a fresh one pops in with a green check.
- Connectors: dashed lines (`stroke-dasharray 14 12`) with packets flowing (`K.flow`) to show traffic or data.
- The terminal types the command that "causes" the scene, from frame 0 when it's the hook.

## Long-form
Terminal top-left, the subject in the left half, the infrastructure it lands on (nodes, clusters, clouds) in the right half; chapters per concept (Pod → Deployment → Service → Ingress), each opening with the command that creates it.

## Recipes
- **"What is X"**: command in the terminal → the object appears → its wrapper/parent springs open around it → what it shares/contains → where it runs → what happens on failure.
- **Architecture**: stack layers top-to-bottom (user → load balancer → pods → DB), draw connectors on their cue words, flow packets once everything is placed.
- **Command explained**: type the command, then highlight each flag in yellow as it is spoken with a label card dropping below it.

## Don't
- The KodeKloud logo, name on screen, mascots or their course UI.
- Real cloud vendor logos unless the user supplies them (use labelled neutral tiles: "Object storage", "Load balancer").
- Fake command output that looks like real tool output; keep example values plausible and list them as illustrative.
