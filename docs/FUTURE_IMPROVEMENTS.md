# Future Improvements

This document tracks planned enhancements and features for future development.

## Error Handling & User Experience

### Priority: High
**Goal**: Improve error visibility and user feedback when messages fail

**Current State**:
- Errors are logged to Cloud Run logs
- Users see generic fallback messages for certain failures
- 401 signature errors fail silently (user sees nothing)
- Rate limit errors show friendly message

**Proposed Improvements**:

1. **User-Facing Error Messages**
   - When message processing fails (after signature verification), send user a helpful error message
   - Examples:
     - "I'm having trouble connecting to my AI backend. Please try again in a moment."
     - "I encountered an error processing your request. The team has been notified."
     - "I'm experiencing high load. Please try again in a few minutes."

2. **Error Categorization**
   - Authentication errors (401, 403)
   - Rate limiting (429, ResourceExhaustedError)
   - Service errors (500, timeouts)
   - Invalid input errors (400)
   - Network errors

3. **Admin Notifications**
   - Send error alerts to Slack admin channel when critical errors occur
   - Include: error type, affected user, agent, timestamp, stack trace
   - Configurable threshold (e.g., alert after 3 consecutive failures)

4. **Error Recovery**
   - Automatic retry logic for transient errors
   - Exponential backoff for rate limits
   - Circuit breaker pattern for failing dependencies

5. **Monitoring Dashboard**
   - Error rate metrics in Cloud Monitoring
   - Custom metrics: message success rate, average latency, error types
   - Alerts for anomalies

**Implementation Notes**:
- Add error handler middleware to catch exceptions in message processing
- Create error response templates for different error types
- Add structured logging with error codes
- Consider using Cloud Error Reporting for automatic error tracking

**Related Files**:
- `app/services/message_processor_v2.py` (lines 198-271: current error handling)
- `app/api/v1/slack_events_v2.py` (webhook error handling)
- `app/core/exceptions.py` (custom exception classes)

---

## Multi-Platform Enhancements

### Self-Service Identity Linking
**Status**: Planned after Google Chat integration

**Goal**: Allow users to link their Slack and Google Chat accounts without admin intervention

**Implementation Options**:
- Linking codes (implemented in IdentityService but not exposed)
- Email verification flow
- OAuth-based linking

---

## Session Management

### Session Analytics
**Goal**: Track session usage and conversation patterns

**Metrics to Track**:
- Session duration
- Message count per session
- Platform switching frequency
- Session timeout rate

---

## Scheduled Jobs

### Multi-Platform Support for Scheduled Jobs
**Status**: Pending (Phase 2 of current work)

**Goal**: Update ScheduledJobExecutor to use unified user_id and support delivery to any platform

**Requirements**:
- Update ScheduledJob model with `user_id` and `output_platform` fields
- Refactor ScheduledJobExecutor to use PlatformConnector
- Migrate existing jobs (or create new)

---

## Developer Experience

### Local Development Improvements
- Docker Compose setup for local testing
- Firestore emulator integration
- Mock Vertex AI service for testing
- Sample agent configurations

### Testing
- Unit tests for platform connectors
- Integration tests for message flow
- End-to-end tests with mock platforms

---

## Documentation

### Tutorials
- Setting up your first agent
- Connecting multiple Slack bots
- Adding Google Chat support
- Managing user identities
- Troubleshooting common issues

### API Documentation
- OpenAPI/Swagger documentation
- Webhook payload examples
- Error response formats

---

## Future Platform Support

### Potential Platforms to Add
- Microsoft Teams
- Discord
- WhatsApp Business API
- Telegram
- Email (via SendGrid/Gmail API)

**Each platform needs**:
- PlatformConnector implementation
- Webhook endpoint
- Authentication handling
- Documentation

---

## Notes

This document should be updated as features are implemented or priorities change.

**Last Updated**: 2026-04-04
**Contributors**: Claude Code
