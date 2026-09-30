"""Keep query strings, cookies and referrers out of optional access logs."""
# U is the URL path without query parameters; r and q would expose preview keys.
access_log_format = '%(h)s %(m)s %(U)s %(s)s %(L)s'
