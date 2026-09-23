import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from news.political_models import (
    PublicFigure,
    PublicFigureOrganisationRelation,
    RegisteredOrganisation,
)


pytestmark = pytest.mark.django_db


def figure():
    return PublicFigure.objects.create(
        canonical_name='Osoba Publiczna', role_category='government', role_title='Minister',
        evidence_url='https://gov.example/minister',
    )


def organisation():
    return RegisteredOrganisation.objects.create(
        name='Fundacja Przykładowa', krs_number='0000123456', kind='foundation',
        official_register_url='https://prs.ms.gov.pl/krs/0000123456',
    )


def test_public_relation_requires_evidence_backed_staff_confirmation():
    relation = PublicFigureOrganisationRelation.objects.create(
        public_figure=figure(), organisation=organisation(), public_role='Członek zarządu',
        evidence_url='https://prs.ms.gov.pl/krs/0000123456',
    )
    staff = get_user_model().objects.create_user(username='editor', is_staff=True)
    relation.confirm(staff)
    relation.refresh_from_db()
    assert relation.verification_status == 'confirmed'
    assert relation.verified_by == staff and relation.verified_at is not None


def test_relation_never_becomes_confirmed_without_a_staff_editor():
    relation = PublicFigureOrganisationRelation(
        public_figure=figure(), organisation=organisation(), public_role='Członek rady',
        evidence_url='https://prs.ms.gov.pl/krs/0000123456', verification_status='confirmed',
    )
    with pytest.raises(ValidationError):
        relation.full_clean()


def test_krs_number_is_limited_to_the_public_identifier_only():
    item = RegisteredOrganisation(
        name='Stowarzyszenie Przykładowe', krs_number='123', kind='association',
        official_register_url='https://prs.ms.gov.pl/krs/0000123456',
    )
    with pytest.raises(ValidationError):
        item.full_clean()


def test_candidate_import_rejects_pesel_and_creates_review_only_relation(tmp_path):
    forbidden = tmp_path / 'forbidden.csv'
    forbidden.write_text('person_name,pesel\nOsoba Publiczna,123\n', encoding='utf-8')
    with pytest.raises(CommandError, match='niedozwolone'):
        call_command('import_public_figure_organisation_candidates', str(forbidden))

    public_figure = figure()
    valid = tmp_path / 'valid.csv'
    valid.write_text(
        'person_name,organisation_name,krs_number,kind,official_register_url,public_role,relation_status,evidence_url,evidence_note\n'
        'Osoba Publiczna,Fundacja Testowa,0000123456,foundation,https://prs.example/1,członkini zarządu,current,https://example.org/dowod,źródło\n',
        encoding='utf-8',
    )
    call_command('import_public_figure_organisation_candidates', str(valid), apply=True)
    relation = PublicFigureOrganisationRelation.objects.get(public_figure=public_figure)
    assert relation.verification_status == 'pending_review'
