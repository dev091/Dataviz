import { expect, test } from "@playwright/test";

const authState = {
  accessToken: "token-123",
  refreshToken: "refresh-123",
  email: "owner@dataviz.com",
  userId: "user-1",
  workspaces: [
    {
      workspace_id: "workspace-1",
      workspace_name: "Executive",
      organization_id: "org-1",
      organization_name: "Northstar Analytics",
      role: "Owner",
    },
  ],
  currentWorkspaceId: "workspace-1",
};

test("dataset catalog exposes AI data prep autopilot plan and feedback loop", async ({ page }) => {
  let approved = 0;
  let isApplied = false;
  const lineage: Array<{ source: string; description: string; affected_fields: string[]; status: string; recorded_at: string | null }> = [
    {
      source: "ingestion_cleaning",
      description: "Column names were standardized during ingestion.",
      affected_fields: ["Order_Date"],
      status: "applied",
      recorded_at: null,
    },
  ];

  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/semantic/datasets", async (route) => {
    await route.fulfill({
      json: [
        {
          id: "dataset-1",
          name: "orders_current",
          source_table: "orders_current.csv",
          physical_table: "ws_orders_current",
          row_count: 4,
          quality_status: "warning",
          quality_profile: {
            overall_score: 78,
            status: "warning",
            duplicate_rows: 1,
            duplicate_ratio: 0.25,
            completeness_score: 97,
            duplicate_score: 60,
            cleaning_score: 93,
            cleaning: {
              rows_before: 4,
              rows_after: 4,
              rows_dropped: 0,
              renamed_columns: { "Order Date": "Order_Date" },
              unnamed_columns_removed: [],
            },
            warnings: ["Column names were standardized during ingestion."],
            field_profiles: [
              {
                name: "Customer_ID",
                data_type: "string",
                null_count: 0,
                null_ratio: 0,
                distinct_count: 3,
                unique_ratio: 0.75,
                sample_values: ["C-100", "C-101"],
                warnings: ["Customer_ID looks like a high-cardinality identifier."],
              },
            ],
          },
          fields: [
            { id: "field-1", name: "Order_Date", data_type: "datetime64[ns]", is_dimension: true, is_metric: false },
            { id: "field-2", name: "Customer_ID", data_type: "object", is_dimension: true, is_metric: false },
            { id: "field-3", name: "Revenue", data_type: "int64", is_dimension: false, is_metric: true },
            { id: "field-4", name: "Cost", data_type: "int64", is_dimension: false, is_metric: true },
          ],
        },
      ],
    });
  });

  await page.route("**/api/v1/semantic/datasets/dataset-1/prep-plan", async (route) => {
    await route.fulfill({
      json: {
        dataset_id: "dataset-1",
        dataset_name: "orders_current",
        dataset_quality_status: "warning",
        generated_at: "2026-03-07T14:00:00Z",
        cleaning_steps: [
          {
            step_id: "dedupe_rows",
            title: "Remove duplicate rows",
            step_type: "deduplicate",
            target_fields: [],
            explanation: "Detected 1 duplicate rows. Deduplicating before modeling will reduce noisy KPI inflation.",
            reversible: true,
            revert_strategy: "Keep the raw synced table unchanged and materialize a cleaned working copy without duplicate rows.",
            sql_preview: "SELECT DISTINCT * FROM source_dataset",
            confidence: 0.91,
            feedback: { approved, rejected: 0 },
            applied: isApplied,
            applied_at: isApplied ? "2026-03-07T14:05:00Z" : null,
          },
          {
            step_id: "mark_identifier:Customer_ID",
            title: "Mark Customer_ID as identifier-only",
            step_type: "semantic_annotation",
            target_fields: ["Customer_ID"],
            explanation: "Customer_ID behaves like an identifier and should not be used as a grouped executive dimension by default.",
            reversible: true,
            revert_strategy: "Keep Customer_ID visible in the raw dataset but restrict its default semantic visibility.",
            sql_preview: null,
            confidence: 0.73,
            feedback: { approved: 0, rejected: 0 },
            applied: false,
            applied_at: null,
          },
        ],
        join_suggestions: [
          {
            target_dataset_id: "dataset-2",
            target_dataset_name: "customers",
            left_field: "Customer_ID",
            right_field: "Customer_ID",
            score: 0.88,
            rationale: "Customer_ID aligns across datasets by name and sampled value overlap.",
          },
        ],
        union_suggestions: [
          {
            target_dataset_id: "dataset-3",
            target_dataset_name: "orders_archive",
            shared_fields: ["Order_Date", "Customer_ID", "Revenue", "Cost"],
            score: 0.92,
            rationale: "orders_current and orders_archive share reporting fields and can likely be stacked.",
          },
        ],
        calculated_field_suggestions: [
          {
            name: "gross_margin",
            expression: "revenue - cost",
            data_type: "number",
            rationale: "Revenue and cost columns exist, so gross margin should be materialized as a reusable governed field.",
          },
        ],
        transformation_lineage: lineage,
        notes: isApplied
          ? ["Applied autopilot steps are recorded in governed prep lineage; raw synced tables remain unchanged until promoted downstream."]
          : [],
      },
    });
  });

  await page.route("**/api/v1/semantic/datasets/dataset-1/prep-feedback", async (route) => {
    approved += 1;
    await route.fulfill({
      json: {
        dataset_id: "dataset-1",
        step_id: "dedupe_rows",
        decision: "approve",
        approved,
        rejected: 0,
        note: "Feedback captured and will influence future prep recommendations.",
      },
    });
  });

  await page.route("**/api/v1/semantic/datasets/dataset-1/prep-actions", async (route) => {
    const body = JSON.parse(route.request().postData() ?? "{}");
    if (body.action === "apply") {
      isApplied = true;
      lineage.unshift({
        source: "ai_data_prep_autopilot",
        description: "Applied prep step 'Remove duplicate rows' through the AI Data Prep Autopilot.",
        affected_fields: [],
        status: "applied",
        recorded_at: "2026-03-07T14:05:00Z",
      });
      await route.fulfill({
        json: {
          dataset_id: "dataset-1",
          step_id: "dedupe_rows",
          action: "apply",
          status: "applied",
          note: "Prep step 'Remove duplicate rows' applied to governed prep history. Raw synced data remains unchanged.",
        },
      });
      return;
    }

    isApplied = false;
    lineage.unshift({
      source: "ai_data_prep_autopilot",
      description: "Rolled back prep step 'Remove duplicate rows' from the AI Data Prep Autopilot.",
      affected_fields: [],
      status: "rolled_back",
      recorded_at: "2026-03-07T14:06:00Z",
    });
    await route.fulfill({
      json: {
        dataset_id: "dataset-1",
        step_id: "dedupe_rows",
        action: "rollback",
        status: "rolled_back",
        note: "Prep step 'Remove duplicate rows' rolled back from governed prep history.",
      },
    });
  });

  await page.goto("/datasets");

  await expect(page.getByRole("heading", { name: "AI Data Prep Autopilot" })).toBeVisible();
  await expect(page.getByText("Remove duplicate rows")).toBeVisible();
  await expect(page.getByText("customers")).toBeVisible();
  await expect(page.getByText("orders_archive", { exact: true })).toBeVisible();
  await expect(page.getByText("gross_margin")).toBeVisible();

  await page.getByRole("button", { name: "Approve step" }).first().click();

  await expect(page.getByText("Feedback captured and will influence future prep recommendations.")).toBeVisible();
  await expect(page.getByText("Approved 1")).toBeVisible();

  await page.getByRole("button", { name: "Apply step" }).first().click();

  await expect(page.getByText("Prep step 'Remove duplicate rows' applied to governed prep history. Raw synced data remains unchanged.")).toBeVisible();
  await expect(page.getByText("Applied", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Applied prep step 'Remove duplicate rows' through the AI Data Prep Autopilot.")).toBeVisible();

  await page.getByRole("button", { name: "Roll back step" }).first().click();

  await expect(page.getByText("Prep step 'Remove duplicate rows' rolled back from governed prep history.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply step" }).first()).toBeVisible();
});
