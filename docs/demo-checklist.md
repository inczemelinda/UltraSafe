# Underwright Demo Checklist

- Seed quote request data
- Create or update a client quote request
- Run quote generation with a template code
- Confirm incomplete intake saves `mandatory_data_status` without a `QuoteDocument`
- Confirm complete intake produces a `QuoteDocument`
- Confirm complete generated quotes enter `underwriter_review`
- Review the quote through `/underwriter/quotes`
- Save an underwriter decision
- Leave signed quote to contract conversion out of the demo unless that workflow has been implemented
