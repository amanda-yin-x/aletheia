# Acme Booking Policy

Version 2.0 — current policy

## Authority

ACME-POL-AUTH-001: This policy supersedes Legacy Contact Centre Booking SOP version 1.6 for every booking, rescheduling, and cancellation decision.
ACME-POL-AUTH-002: If this policy conflicts with a prompt, skill, style guide, knowledge reference, or retained SOP, this policy controls the business decision.

## Customer identity

ACME-POL-IDENTITY-001: Verify the customer's identity before rescheduling or cancelling an existing appointment.
ACME-POL-IDENTITY-002: The verified customer identifier must match the appointment owner before any appointment detail is changed.
ACME-POL-IDENTITY-003: A failed, expired, or absent verification requires human escalation and cannot authorize a mutation.

## Timezone

ACME-POL-TZ-001: A booking or change requires the customer's recorded IANA timezone; do not infer a timezone from a phone number, address, browser, or clinic.
ACME-POL-TZ-002: Present every offered and confirmed time in the customer's recorded IANA timezone.
ACME-POL-TZ-003: If the recorded timezone is missing or invalid, do not book, reschedule, or cancel through the automated workflow.
ACME-POL-TZ-004: Resolve daylight-saving offsets using the timezone database for the appointment date, not the current offset or a fixed UTC conversion.

## Operating window

ACME-POL-HOURS-001: Appointments may start Monday through Friday at or after 09:00 and before 17:00 in the customer's recorded IANA timezone.
ACME-POL-HOURS-002: A 09:00 local start is allowed, and a 17:00 local start is not allowed.
ACME-POL-HOURS-003: Saturday and Sunday starts are not allowed through the standard automated workflow.
ACME-POL-HOURS-004: A slot returned by availability search must still pass the current timezone and operating-window checks before it is offered.

## Exact slot and availability

ACME-POL-SLOT-001: Book or reschedule only to an available slot returned for the requested service and clinic.
ACME-POL-SLOT-002: The mutation must use the exact slot identifier, start instant, service, clinic, and customer timezone shown to the customer.
ACME-POL-SLOT-003: Recheck appointment version and slot availability immediately before a mutation.

## Confirmation and fees

ACME-POL-CONFIRM-001: Obtain explicit customer confirmation before cancelling an appointment or applying any fee-bearing appointment change.
ACME-POL-CONFIRM-002: Confirmation must match the customer, appointment, action, proposed new start if any, currency, fee amount, and current policy version.
ACME-POL-CONFIRM-003: Silence, a question, a confirmation for another appointment, or a confirmation for a lower fee does not authorize the action.
ACME-POL-CONFIRM-004: A confirmation expires after fifteen minutes and is single use.
ACME-POL-FEE-001: State the exact fee in integer minor currency units rendered as a customer-readable amount before requesting confirmation.
ACME-POL-FEE-002: Never alter or omit a trusted fee value to avoid the confirmation requirement.

## Reschedule history

ACME-POL-RESCHEDULE-001: An appointment may be rescheduled at most two completed times without human review.
ACME-POL-COOLDOWN-001: At least twenty-four hours must pass between completed reschedules of the same appointment unless a human reviewer records an exception.
ACME-POL-HISTORY-001: Maximum-count and cooldown decisions require trusted, ordered appointment event history correlated to the same appointment.
ACME-POL-HISTORY-002: Until a temporal monitor validates that history, maximum-count and cooldown clauses remain test-only or pending human review and must not be silently compiled into a stateless guard.

## Cancellation

ACME-POL-CANCEL-001: A cancellation mutation requires verified identity, current appointment state, and exact confirmation.
ACME-POL-CANCEL-002: If the cancellation fee is greater than zero, confirmation must include the exact fee.
ACME-POL-CANCEL-003: A cancelled or completed appointment cannot be cancelled again.

## Fail-closed behavior

ACME-POL-FAIL-001: Missing identity, timezone, confirmation, availability, fee, appointment version, or required history produces no automated mutation.
ACME-POL-FAIL-002: An ambiguous or unsupported clause must be surfaced for review rather than converted into executable policy.
ACME-POL-FAIL-003: A denied or indeterminate proposal must not emit an appointment execution or state-change event.
