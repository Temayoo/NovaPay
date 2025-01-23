from celery import shared_task
from sqlalchemy.orm import Session
from models import CompteBancaire, Transaction, PrelevementAutomatique
from crud import create_transaction

@shared_task
def effectuer_prelevement_automatique(db_session):
    db = Session(bind=db_session)
    prelevements = db.query(PrelevementAutomatique).all()

    for prelevement in prelevements:
        compte_envoyeur = db.query(CompteBancaire).filter(CompteBancaire.id == prelevement.compte_bancaire_id).first()
        compte_receveur = db.query(CompteBancaire).filter(CompteBancaire.id == prelevement.compte_bancaire_id).first()

        if compte_envoyeur and compte_receveur and compte_envoyeur.solde >= prelevement.montant:
            # Créez la transaction
            transaction = create_transaction(
                db=db,
                transaction={
                    'montant': prelevement.montant,
                    'description': 'Prélèvement automatique',
                    'compte_envoyeur': compte_envoyeur.iban,
                    'compte_receveur': compte_receveur.iban,
                },
                compte_envoyeur=compte_envoyeur,
                compte_receveur=compte_receveur,
                status=1,
            )
    db.commit()
