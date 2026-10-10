# Identidad de report-gen 0.16.0

Modo: edición de imagen con conservación de identidad. Referencia:
`docs/img/report-gen-logo.png`. Recurso final: `webapp/static/brand-mark.png`.

Optimización posterior (0.23.1): la interfaz usa `webapp/static/brand-mark.webp`,
una copia de 900 × 600 px codificada sin pérdidas tras un único reescalado Lanczos.
El PNG de 900 × 600 px se conserva para las referencias documentales anteriores.
Ambas variantes preservan la proporción 3:2 y la transparencia del recurso original;
el diseño y los rasgos de los perros no se regeneraron.

Prometeo y Evaristo conservan los rasgos de la referencia. La imagen no incorpora
el nombre: el texto report-gen se presenta en HTML para evitar cortes y conservar
legibilidad. El favicon de la pata sigue disponible como marca a tamaño pequeño.

Prompt de generación:

Use case: identity-preserve / logo-brand. Edit target: the supplied report-gen logo.
Create a refined professional pixel-art emblem for a pentesting report workspace,
using exactly the same TWO pet dogs as the reference. Preserve the left orange-and-white
corgi with upright ears, white facial blaze and chest; preserve the right scruffy black
terrier with white muzzle/chest and BOTH front paws with white socks. Both dogs are
equally prominent, alert, friendly, recognizable, no extra animals. Redesign into a
compact, balanced paired portrait with their four front paws resting on the top edge
of a minimal dark navy terminal panel. The panel is shallow and has only a small clean
phosphor-green >_ prompt centered on it; NO words, NO Report Gen lettering, no tiny text.
Remove the hearts, starbursts, orange paw symbol and gold sign frame. Crisp deliberate
pixel silhouettes, simplified fur clusters, restrained three-level shading, professional
16-bit pixel craft, no glossy 3D or neon glow. Preserve natural dog colors; navy outline
and a subtle pale-green terminal edge supply the hacker/pentester identity. No hoodies,
masks, weapons or aggressive expressions. Emblem must remain clear at small dashboard
sizes. Center the whole mark with comfortable transparent margins, broad landscape
silhouette roughly 3:2 inside a transparent canvas. Genuine transparent background,
clean alpha, no checkerboard drawn into the image. Output one final emblem, not a sheet
of variants or a mockup.
