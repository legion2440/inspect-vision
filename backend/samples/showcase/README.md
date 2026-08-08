# Current showcase assets

The current operator showcase does not store dataset image binaries in Git.
`backend/samples/showcase-samples.json` pins eight MVTec AD good/bad entries to a
specific MMAD mirror revision, and `/api/samples/{id}/image` proxies those source
bytes by manifest ID.

Legacy PCB, steel, and concrete showcase image copies were removed when the
operator sample catalog changed to Bottle, Capsule, Screw, and Metal nut pairs.
Historical provenance and recorded evidence remain in their dedicated locations.
