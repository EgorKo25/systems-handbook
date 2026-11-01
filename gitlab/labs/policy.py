"""Small explicit model of this lab's workflow; NOT a GitLab YAML evaluator."""
def pipeline_allowed(source, branch=None, open_merge_requests=False, tag=None):
    if source == 'merge_request_event':
        return True
    if source == 'push' and branch and open_merge_requests:
        return False
    if source in ('push', 'web'):
        return True
    return False


def release_job(source, tag=None):
    """Model only the worked example in chapter 06, not the actual lab jobs."""
    if tag:
        return 'automatic'
    if source == 'web':
        return 'manual-blocking'
    return 'absent'
