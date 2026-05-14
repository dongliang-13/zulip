"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const user_tasks_assignment = zrequire("user_tasks_assignment");

run_test("resolve_assignee_email prefers delivery_email", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        delivery_email: "zoe@example.com",
        email: "zoe+legacy@example.com",
    });

    assert.equal(email, "zoe@example.com");
});

run_test("resolve_assignee_email trims preferred delivery_email", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        delivery_email: "  zoe@example.com  ",
        email: "zoe+legacy@example.com",
    });

    assert.equal(email, "zoe@example.com");
});

run_test("resolve_assignee_email falls back to email", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        email: "zoe@example.com",
    });

    assert.equal(email, "zoe@example.com");
});

run_test("resolve_assignee_email returns empty string when unavailable", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        full_name: "Zoe",
    });

    assert.equal(email, "");
});

run_test("resolve_assignee_email ignores whitespace-only fields", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        delivery_email: "   ",
        email: "   ",
    });

    assert.equal(email, "");
});

run_test("resolve_assignee_email trims fallback email", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        delivery_email: "   ",
        email: "  zoe@example.com  ",
    });

    assert.equal(email, "zoe@example.com");
});

run_test("resolve_assignee_email normalizes email to lowercase", () => {
    // normalize_email() calls .toLowerCase() so the backend receives a
    // consistent casing; the backend uses __iexact for lookup, so this
    // is safe and intentional.
    const email = user_tasks_assignment.resolve_assignee_email({
        email: "AARON@zulip.com",
    });

    assert.equal(email, "aaron@zulip.com");
});

run_test("resolve_assignee_email normalizes delivery_email to lowercase", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        delivery_email: "ZOEIP@EXAMPLE.COM",
        email: "zoe@example.com",
    });

    assert.equal(email, "zoeip@example.com");
});
