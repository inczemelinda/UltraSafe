import { expect, test } from "playwright/test";
import { demoClient, quoteDemoData } from "./demo-data";
import {
  checkOption,
  chooseVisibleSelectOption,
  clickWithCursor,
  clickNext,
  expectVisible,
  fillByLabel,
  installDemoCursor,
  pause,
  resetDemoBrowserState
} from "./helpers";

test.describe("client quote demo recording", () => {
  test("home page to client login to quote estimate", async ({ page }) => {
    await resetDemoBrowserState(page);

    await page.goto("/");
    await installDemoCursor(page);
    await expectVisible(page.getByRole("heading", { name: "Fast digital insurance" }));
    await pause(page, 300);

    await clickWithCursor(page, page.getByRole("link", { name: "Get a Quote" }));
    await expectVisible(page.getByRole("button", { name: "Sign In" }));
    await fillByLabel(page, "Email", demoClient.email);
    await fillByLabel(page, "Password", demoClient.password);
    await pause(page, 120);
    await clickWithCursor(page, page.getByRole("button", { name: "Sign In" }));

    await expect(page).toHaveURL(/\/client$/);
    await expectVisible(page.getByRole("link", { name: "Get a Quote" }));
    await pause(page, 300);

    await clickWithCursor(page, page.getByRole("link", { name: "Get a Quote" }));
    await expect(page).toHaveURL(/\/client\/quote\/new$/);
    await expectVisible(page.getByText("Anual Premium Price"));
    await pause(page, 250);

    await fillByLabel(page, "Expected coverage amount (RON)", quoteDemoData.coverageAmount);
    await expectVisible(page.getByText("Final preview"));
    await clickNext(page);

    await chooseVisibleSelectOption(page, quoteDemoData.propertyType);
    await clickNext(page);

    await fillByLabel(page, "Country", quoteDemoData.address.country);
    await fillByLabel(page, "County", quoteDemoData.address.county);
    await fillByLabel(page, "City", quoteDemoData.address.city);
    await fillByLabel(page, "Street", quoteDemoData.address.street);
    await fillByLabel(page, "Number", quoteDemoData.address.number);
    await fillByLabel(page, "Postal code", quoteDemoData.address.postalCode);
    await clickNext(page);

    await fillByLabel(page, "What year was the property built?", quoteDemoData.yearBuilt);
    await clickNext(page);

    await fillByLabel(page, "Size in m²", quoteDemoData.sizeSqm);
    await clickNext(page);

    await chooseVisibleSelectOption(page, quoteDemoData.constructionType);
    await clickNext(page);

    await chooseVisibleSelectOption(page, quoteDemoData.usageType);
    await clickNext(page);

    await chooseVisibleSelectOption(page, quoteDemoData.hadClaims);
    await clickNext(page);

    for (const feature of quoteDemoData.securityFeatures) {
      await checkOption(page, feature);
      await pause(page, 50);
    }
    await clickNext(page);

    await fillByLabel(page, "Full name", quoteDemoData.contact.fullName);
    await fillByLabel(page, "Email", quoteDemoData.contact.email);
    await fillByLabel(page, "Phone number", quoteDemoData.contact.phone);
    await fillByLabel(page, "ID", quoteDemoData.contact.nationalId);
    await expectVisible(page.getByRole("button", { name: "Submit" }));
    await expectVisible(page.getByText("Final preview"));
    await pause(page, 200);
    await clickWithCursor(page, page.getByRole("button", { name: "Submit" }));
    await expectVisible(page.getByRole("heading", { name: "Thank you for completing the quote." }));

    await pause(page, 1_000);
  });
});
