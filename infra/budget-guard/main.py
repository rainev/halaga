"""Cloud Function — the real hard cap on GCP spend.

A Cloud Billing budget on its own is only an *alert* (see docs/DEPLOY-staging.md).
This function is what turns it into a hard stop: it's triggered by the budget's
Pub/Sub notifications, and when actual cost reaches the budget it **unlinks the
billing account from the project**, which halts every billable resource (Cloud
Run stops serving). Staging goes offline instead of running up a bill.

Re-enable after investigating with:
    gcloud billing projects link finsight-staging --billing-account=<ACCOUNT_ID>
"""

import base64
import json
import os

import functions_framework
from googleapiclient import discovery

PROJECT_ID = os.environ["GUARD_PROJECT_ID"]
PROJECT_NAME = f"projects/{PROJECT_ID}"

# cache_discovery=False avoids a noisy warning on the function's read-only FS.
_billing = discovery.build("cloudbilling", "v1", cache_discovery=False)


@functions_framework.cloud_event
def stop_billing(cloud_event):
    envelope = cloud_event.data["message"]
    payload = json.loads(base64.b64decode(envelope["data"]).decode("utf-8"))

    cost = float(payload.get("costAmount", 0))
    budget = float(payload.get("budgetAmount", 0))
    print(f"budget notification: cost={cost} budget={budget}")

    # Only act at/over 100% of the budget. Lower-threshold notifications
    # (50%, 90%) still arrive here — they're just informational.
    if budget <= 0 or cost < budget:
        print("under budget; no action")
        return

    info = _billing.projects().getBillingInfo(name=PROJECT_NAME).execute()
    if not info.get("billingEnabled"):
        print("billing already disabled; nothing to do")
        return

    # Empty billingAccountName == unlink == disable billing on the project.
    _billing.projects().updateBillingInfo(
        name=PROJECT_NAME, body={"billingAccountName": ""}
    ).execute()
    print(f"DISABLED billing on {PROJECT_ID}: cost {cost} >= budget {budget}")
