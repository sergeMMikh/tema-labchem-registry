"""Summarize CI security reports without contacting or modifying the live site."""

import json
import os
from pathlib import Path

blockers = []
summary = []


def load_json(filename):
    path = Path(filename)
    if not path.is_file() or not path.stat().st_size:
        blockers.append(f'{filename}: report is missing or empty')
        return {}
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        blockers.append(f'{filename}: invalid JSON ({error})')
        return {}
    if not isinstance(report, dict):
        blockers.append(f'{filename}: expected a JSON object')
        return {}
    return report


def count_trivy(filename):
    report = load_json(filename)
    counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'UNKNOWN': 0}
    findings = []
    results = report.get('Results', [])
    if not isinstance(results, list):
        blockers.append(f'{filename}: invalid Results list')
        return counts, findings
    for result in results:
        if not isinstance(result, dict):
            continue
        for category in ('Vulnerabilities', 'Misconfigurations', 'Secrets'):
            for finding in result.get(category) or []:
                severity = str(finding.get('Severity', 'UNKNOWN')).upper()
                counts[severity if severity in counts else 'UNKNOWN'] += 1
                if severity in ('CRITICAL', 'HIGH'):
                    findings.append({
                        'report': filename,
                        'target': result.get('Target', ''),
                        'type': category,
                        'severity': severity,
                        'id': finding.get('VulnerabilityID') or finding.get('ID', ''),
                        'package': finding.get('PkgName', ''),
                        'version': finding.get('InstalledVersion', ''),
                        'fixed_version': finding.get('FixedVersion', ''),
                        'title': finding.get('Title', ''),
                    })
    return counts, findings


def main():
    secret_report = Path('trufflehog-report.json')
    if not secret_report.is_file():
        blockers.append('trufflehog-report.json: report is missing')
    verified = 0
    if secret_report.is_file():
        for number, line in enumerate(secret_report.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            try:
                finding = json.loads(line)
            except ValueError:
                blockers.append(f'trufflehog-report.json: invalid JSON on line {number}')
                continue
            if finding.get('Verified') is True:
                verified += 1
    summary.append(f'TruffleHog verified secrets: {verified}')
    if verified:
        blockers.append(f'TruffleHog: {verified} verified secret(s)')

    bandit = load_json('bandit-report.json')
    bandit_high = sum(
        str(finding.get('issue_severity', '')).upper() == 'HIGH'
        for finding in bandit.get('results', [])
    )
    summary.append(f'Bandit HIGH findings: {bandit_high}')
    if bandit_high:
        blockers.append(f'Bandit: {bandit_high} HIGH finding(s)')

    audit = load_json('pip-audit-report.json')
    audit_count = sum(
        len(dependency.get('vulns', [])) for dependency in audit.get('dependencies', [])
    )
    summary.append(f'pip-audit vulnerabilities: {audit_count} (report only)')

    fs, fs_findings = count_trivy('trivy-fs-report.json')
    config, config_findings = count_trivy('trivy-config-report.json')
    image, image_findings = count_trivy('trivy-image-report.json')
    trivy_findings = fs_findings + config_findings + image_findings
    for name, counts in (('filesystem', fs), ('config', config), ('image', image)):
        values = ', '.join(f'{key}={value}' for key, value in counts.items())
        summary.append(f'Trivy {name}: {values}')
        if name != 'config' and (counts['CRITICAL'] or counts['HIGH']):
            blockers.append(
                f"Trivy {name}: CRITICAL={counts['CRITICAL']}, HIGH={counts['HIGH']}"
            )

    semgrep = Path('semgrep-report.json')
    summary.append('Semgrep: report available' if semgrep.is_file() else 'Semgrep: no report')

    status = 'BLOCKED' if blockers else 'PASSED'
    report = {
        'status': status,
        'summary': summary,
        'blockers': blockers,
        'trivy_findings': trivy_findings,
        'pipeline': os.getenv('CI_PIPELINE_URL', ''),
        'commit': os.getenv('CI_COMMIT_SHA', ''),
    }
    Path('security-gateway-report.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    markdown = [
        '# Security Gateway Report',
        '',
        f'Status: **{status}**',
        '',
        '## Summary',
        '',
        *(f'- {item}' for item in summary),
        '',
        '## Policy',
        '',
        '- Verified secrets, Bandit HIGH, Trivy filesystem/image CRITICAL or HIGH: block.',
        '- pip-audit, Semgrep, and Trivy config: report only.',
        '- Missing or invalid required reports: block.',
        '',
        '## Blockers',
        '',
        *(f'- {item}' for item in blockers or ['None']),
        '',
        '## Trivy HIGH and CRITICAL findings',
        '',
        *(
            '- {severity} {type}: {id} {package} {version} (fixed: {fixed_version}) — {title} [{report}: {target}]'.format(**finding)
            for finding in trivy_findings
        ),
    ]
    Path('security-gateway-report.md').write_text('\n'.join(markdown) + '\n', encoding='utf-8')
    print('\n'.join(summary))
    print(f'Security gateway: {status}')
    for item in blockers:
        print(f'- {item}')
    return bool(blockers)


if __name__ == '__main__':
    raise SystemExit(main())
