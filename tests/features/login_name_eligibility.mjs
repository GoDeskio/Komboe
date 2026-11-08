import assert from "node:assert/strict";
import test from "node:test";

import { loginNameWrapAllowed } from "../../clients/upstream/libs/common/src/auth/kdf-identity.ts";

test("login name eligibility matches the server wrap rule", () => {
  assert.equal(loginNameWrapAllowed(0, 100000), true);
  assert.equal(loginNameWrapAllowed(0, 500000), true);
  assert.equal(loginNameWrapAllowed(0, 600000), true);
  assert.equal(loginNameWrapAllowed(0, 600001), false);
  assert.equal(loginNameWrapAllowed(0, 750000), false);
  assert.equal(loginNameWrapAllowed(0, 5000), false);
  assert.equal(loginNameWrapAllowed(1, 3), false);
  assert.equal(loginNameWrapAllowed(1, 600000), false);
});
