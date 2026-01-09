import typing

import pandas as pd

from soongo_data.connectors import Dataset, DataSource, attach_dataset, get_latest_file
from soongo_data.data_models import (
    CollaboratorsModel,
    MileageReportsModel,
    TaxesModel,
    VehicleAssociationsModel,
    VehicleContractsModel,
    VehicleMaintenanceModel,
    VehiclesModel,
)
from soongo_data.utils.enums import (
    AssignmentType,
    ContractType,
    EnergyTypes,
    InKindBenefitType,
    Makes,
    Models,
    Suppliers,
    SynchronizationTypes,
    VehicleStatus,
    mapper_factory,
)
from soongo_data.utils.type import (
    DateConverter,
    NamesConverter,
    PlateConverter,
    convert_numeric,
    convert_string,
    str_is_nan,
)


class AcorusCsvUploadData(Dataset):
    CONNECTOR_NAME = "ACORUS"
    NAME = "CSV_UPLOAD"
    TYPE = SynchronizationTypes.csv_upload.value


@attach_dataset(AcorusCsvUploadData)
class AcorusVerdoneSource(DataSource):
    NAME = "VERDONE_FLEET"

    def __fetch__(self: typing.Self) -> typing.Collection[str]:
        return (
            get_latest_file(
                target_folder=self.folder,
                pattern="SOCIETE VERDONE A INTERGRER .xlsx",
                s3_bucket=self.s3_bucket,
            ),
        )

    def __parse__(
        self: typing.Self,
        data_path: typing.Sequence[str],
        **parsing_params: typing.Dict[str, typing.Any],
    ) -> typing.Optional[pd.DataFrame]:
        if len(data_path) > 1:
            raise ValueError(f"Only one file path expected but {len(data_path)} passed")

        vehicle_df = self.load_table(
            file_path=data_path[0],
            col_lst=[
                VehiclesModel.make.return_variant(
                    raw_name="Marque",
                ),
                VehiclesModel.model.return_variant(
                    raw_name="type",
                ),
                VehiclesModel.plate_number.return_variant(
                    raw_name="Immat.",
                    post_processing=PlateConverter(
                        org_slug=self.organization_name,
                        raise_errors=False,
                    ),
                ),
                VehiclesModel.fiscal_type.return_variant(
                    raw_name="Genre",
                ),
                VehiclesModel.fiscal_power.return_variant(
                    raw_name="Puiss.",
                    post_processing=lambda x: convert_numeric(convert_string(x).str.replace("CV", "")),
                    dtype="Int64",
                ),
                VehiclesModel.entry_into_fleet_date.return_variant(
                    raw_name="date acquisition",
                    post_processing=DateConverter(r"%d/%m/%Y"),
                ),
                MileageReportsModel.mileage.return_variant(
                    raw_name="NB KM 31/01/2025",
                ),
                VehicleContractsModel.contract_type.return_variant(
                    raw_name="Financement",
                ),
                VehicleContractsModel.lease_months.return_variant(
                    raw_name="durée",
                    post_processing=lambda x: convert_numeric(convert_string(x).str.replace(" mois", "")),
                ),
                VehiclesModel.rebate_price.return_variant(
                    raw_name="prix achat",
                ),
                VehicleContractsModel.total_rent_net.return_variant(
                    raw_name="Montant loyer ou échéance",
                ),
                VehicleContractsModel.lease_end_date.return_variant(
                    raw_name="date de fin",
                ),
                VehicleMaintenanceModel.maintenance_date.return_variant(
                    raw_name="CT",
                ),
                VehicleMaintenanceModel.pollution_control_date,
            ],
            record_dates=[VehiclesModel.entry_into_fleet_date.name],
            skip_cols=[
                "Utilisateur",
                "service",
                "Montant Vignette",
                "TVTS",
                "Unnamed: 1",
                "Solde restant dû",
                "amortis.",
                "valeur résiduelle",
                "Côte Argus au 24/11/05",
                "Contrôle technique",
            ],
            skiprows=[0, 1],
        )
        # Acorus informed us their Verdone BU acquired all their cars through SOGELEASE
        vehicle_df[VehiclesModel.car_supplier.name] = Suppliers.sogelease.value.name
        vehicle_df[VehiclesModel.vehicle_status.name] = VehicleStatus.active.value

        vehicle_df[VehicleContractsModel.lease_start_date.name] = vehicle_df[VehiclesModel.entry_into_fleet_date.name]
        vehicle_df[MileageReportsModel.mileage_date.name] = pd.to_datetime("31/01/2025")  # Hardcoded in column name

        return vehicle_df


@attach_dataset(AcorusCsvUploadData)
class AcorusEneorSource(DataSource):
    NAME = "ENEOR_FLEET"

    def __fetch__(self: typing.Self) -> typing.Collection[str]:
        return (
            get_latest_file(
                target_folder=self.folder,
                pattern="ENEOR.xlsx",
                s3_bucket=self.s3_bucket,
            ),
        )

    def __parse__(
        self: typing.Self,
        data_path: typing.Collection[str],
    ) -> pd.DataFrame:
        if len(data_path) > 1:
            raise ValueError(f"Only one file path expected but {len(data_path)} passed")

        vehicle_df = self.load_table(
            file_path=data_path[0],
            col_lst=[
                VehiclesModel.car_supplier.return_variant(
                    raw_name="FOURNISSEUR", post_processing=lambda x: mapper_factory(Suppliers)(x.replace("ACORUS", ""))
                ),
                VehiclesModel.full_model.return_variant(
                    raw_name="PRODUIT",
                ),
                VehiclesModel.plate_number.return_variant(
                    raw_name="IMMATRICULATION",
                    post_processing=PlateConverter(
                        org_slug=self.organization_name,
                        raise_errors=False,
                    ),
                ),
                VehicleContractsModel.contract_reference.return_variant(
                    raw_name="N° DE CONTRAT",
                ),
                VehicleContractsModel.lease_start_date.return_variant(
                    raw_name="DEBUT DU CONTRAT",
                    post_processing=DateConverter(r"%d/%m/%Y"),
                ),
                VehicleContractsModel.lease_end_date.return_variant(
                    raw_name="RESTITUTION PREVUE",
                    post_processing=DateConverter(r"%d/%m/%Y"),
                ),
                VehicleContractsModel.lease_mileage.return_variant(raw_name="KM CONTRACTUEL"),
                VehicleContractsModel.total_rent_ttc.return_variant(raw_name="MONTANT TTC"),
                VehicleContractsModel.lease_months.return_variant(raw_name="DUREE (mois)"),
                VehicleMaintenanceModel.maintenance_date.return_variant(
                    raw_name="REVISIONS.2",
                    post_processing=DateConverter(r"%d/%m/%Y"),
                ),
            ],
            record_dates=[
                VehicleContractsModel.lease_start_date.name,
            ],
            skip_cols=[
                "N° DE CLIENT",
                "ENTITE",
                "COMMENTAIRES",
                "REVISIONS",
                "REVISIONS.1",
                "INFO",
            ],
        )
        vehicle_df = vehicle_df.loc[~str_is_nan(vehicle_df[VehiclesModel.plate_number.name])]
        vehicle_df[VehiclesModel.vehicle_status.name] = VehicleStatus.active.value
        vehicle_df[VehiclesModel.entry_into_fleet_date.name] = vehicle_df[VehicleContractsModel.lease_start_date.name]
        vehicle_df[VehiclesModel.model.name] = vehicle_df[VehiclesModel.full_model.name].map(
            {
                "CLIO ZEN E-TECH 140": Models.clio.value,
                "CLIO HYB - 44": Models.clio.value,
                "CLIO HYB  - 69": Models.clio.value,
                "YARIS -> w/ entretien + assu.": Models.yaris.value,
                "VW SKODA OCTAVIA -> w/ entretien + assu.": Models.octavia.value,
                "TESLA 3": Models.model_3.value,
                "HUYNDAI KONA": Models.kona.value,
            }
        )
        vehicle_df[VehiclesModel.make.name] = vehicle_df[VehiclesModel.full_model.name].map(
            {
                "CLIO ZEN E-TECH 140": Makes.renault.value,
                "CLIO HYB - 44": Makes.renault.value,
                "CLIO HYB  - 69": Makes.renault.value,
                "YARIS -> w/ entretien + assu.": Makes.toyota.value,
                "VW SKODA OCTAVIA -> w/ entretien + assu.": Makes.skoda.value,
                "TESLA 3": Makes.tesla.value,
                "HUYNDAI KONA": Makes.hyundai.value,
            }
        )
        vehicle_df[VehiclesModel.energy.name] = vehicle_df[VehiclesModel.full_model.name].map(
            {
                "CLIO ZEN E-TECH 140": EnergyTypes.gaz_hybrid_no_recharge.value,
                "CLIO HYB - 44": EnergyTypes.gaz_hybrid_no_recharge.value,
                "CLIO HYB  - 69": EnergyTypes.gaz_hybrid_no_recharge.value,
                "TESLA 3": EnergyTypes.electric.value,
            }
        )

        return vehicle_df


@attach_dataset(AcorusCsvUploadData)
class AcorusIkbHistorySource(DataSource):
    NAME = "IKB_HISTORY"

    def __fetch__(self: typing.Self) -> typing.Collection[str]:
        return (
            get_latest_file(
                target_folder=self.folder,
                pattern="aen_historique.csv",
                s3_bucket=self.s3_bucket,
            ),
        )

    def __parse__(
        self: typing.Self,
        data_path: typing.Sequence[str],
    ) -> pd.DataFrame:
        """
        Imports the AEN history from the CSV files.
        """
        if len(data_path) > 1:
            raise ValueError(f"Only one file path expected but {len(data_path)} passed")

        aen_df = self.load_table(
            file_path=data_path[0],
            col_lst=[
                TaxesModel.ikb_start_date.return_variant(
                    raw_name="Mois",
                    post_processing=DateConverter(r"%d/%m/%Y"),
                ),
                CollaboratorsModel.organization_collaborator_id.return_variant(
                    raw_name="Matricule",
                ),
                CollaboratorsModel.employee_full_name.return_variant(
                    raw_name="Salarié",
                    post_processing=lambda x: (
                        NamesConverter(self.organization_name)(
                            convert_string(x).str.replace(
                                r" (?:née|époux(se)).*$",
                                "",
                                regex=True,
                            )
                        )
                    ),
                ),
                TaxesModel.ikb_monthly_value.return_variant(
                    raw_name="Résultat\nsalarial",
                    post_processing=convert_numeric,
                ),
            ],
            record_dates=[],
            skip_cols=[
                "Code\nlibellé",
                "Libellé",
                "Base\nsalariale",
                "Taux/montant\nsalarial",
                "Taux/montant\npatronal",
                "Base\npatronale",
                "Résultat\npatronal",
            ],
            encoding="utf8",
        )

        aen_df = aen_df.sort_values(
            by=[
                CollaboratorsModel.employee_full_name.name,
                CollaboratorsModel.organization_collaborator_id.name,
                TaxesModel.ikb_start_date.name,
            ],
            ascending=True,
        )

        aen_df[TaxesModel.ikb_monthly_value.name] = -aen_df[TaxesModel.ikb_monthly_value.name].fillna(0)
        aen_df[TaxesModel.ikb_end_date.name] = aen_df[TaxesModel.ikb_start_date.name] + pd.offsets.MonthEnd(0)
        aen_df[TaxesModel.ikb_type.name] = InKindBenefitType.recurring.value

        if self.organization_name == "acorus":
            # In Acorus the unique id is the email. But here we can map
            # the organization_collaborator_id to a specific collaborator.
            aen_df[CollaboratorsModel.email.name] = aen_df[CollaboratorsModel.organization_collaborator_id.name].map(
                {
                    "1903": "julien.deoliveira@groupe-acorus.fr",
                }
            )

        return aen_df


@attach_dataset(AcorusCsvUploadData)
class AcorusIkbDirectionSource(DataSource):
    NAME = "IKB_DIRECTION"

    def __fetch__(self: typing.Self) -> typing.Collection[str]:
        return (
            get_latest_file(
                target_folder=self.folder,
                pattern="AVN 2022 2025 Groupe.xlsx",
                s3_bucket=self.s3_bucket,
            ),
        )

    def __parse__(
        self: typing.Self,
        data_path: typing.Sequence[str],
    ) -> pd.DataFrame:
        """
        Imports the AEN history from the CSV files.
        """
        if len(data_path) > 1:
            raise ValueError(f"Only one file path expected but {len(data_path)} passed")

        aen_df = self.load_table(
            file_path=data_path[0],
            col_lst=[
                TaxesModel.ikb_start_date.return_variant(
                    raw_name="Mois",
                    post_processing=DateConverter(r"%d/%m/%Y"),
                ),
                CollaboratorsModel.organization_collaborator_id.return_variant(
                    raw_name="Matricule",
                ),
                CollaboratorsModel.employee_full_name.return_variant(
                    raw_name="Salarié",
                    post_processing=lambda x: (
                        NamesConverter(self.organization_name)(
                            convert_string(x).str.replace(
                                r" (?:née|époux(se)).*$",
                                "",
                                regex=True,
                            )
                        )
                    ),
                ),
                TaxesModel.ikb_monthly_value.return_variant(
                    raw_name="Résultat\nsalarial",
                    post_processing=convert_numeric,
                ),
            ],
            record_dates=[],
            skip_cols=[
                "Code\nlibellé",
                "Libellé",
                "Base\nsalariale",
                "Taux/montant\nsalarial",
                "Taux/montant\npatronal",
                "Base\npatronale",
                "Résultat\npatronal",
            ],
            use_sheets=["*"],
        )

        aen_df = aen_df.sort_values(
            by=[
                CollaboratorsModel.employee_full_name.name,
                CollaboratorsModel.organization_collaborator_id.name,
                TaxesModel.ikb_start_date.name,
            ],
            ascending=True,
        )
        # TODO: confirm with Samia that Cloisol negative values should be positive
        aen_df[TaxesModel.ikb_monthly_value.name] = aen_df[TaxesModel.ikb_monthly_value.name].abs().fillna(0)

        aen_df[TaxesModel.ikb_end_date.name] = aen_df[TaxesModel.ikb_start_date.name] + pd.offsets.MonthEnd(0)

        aen_df[TaxesModel.ikb_type.name] = InKindBenefitType.recurring.value

        return aen_df


@attach_dataset(AcorusCsvUploadData)
class AcorusSertraSource(DataSource):
    NAME = "SERTRA"

    def __fetch__(self: typing.Self) -> typing.Collection[str]:
        return (
            get_latest_file(
                target_folder=self.folder,
                pattern="TABLEAU VEHICULES 2025.xlsx",
                s3_bucket=self.s3_bucket,
            ),
        )

    def __parse__(
        self: typing.Self,
        data_path: typing.Sequence[str],
        **parsing_params: typing.Dict[str, typing.Any],
    ) -> typing.Optional[pd.DataFrame]:
        if len(data_path) > 1:
            raise ValueError(f"Only one file path expected but {len(data_path)} passed")

        vehicle_df = self.load_table(
            file_path=data_path[0],
            col_lst=[
                VehiclesModel.full_model.return_variant(
                    raw_name="Type Véhicule",
                ),
                VehiclesModel.plate_number.return_variant(
                    raw_name="N° Immatricul.",
                    post_processing=PlateConverter(
                        org_slug=self.organization_name,
                    ),
                ),
                VehicleContractsModel.contract_type.return_variant(
                    raw_name="Type Contrat",
                    post_processing=None,
                ),
                VehiclesModel.car_supplier.return_variant(
                    raw_name="Loueur",
                    post_processing=None,
                ),
                VehicleContractsModel.lease_start_date.return_variant(
                    raw_name="Début", post_processing=DateConverter(date_format=r"%m/%d/%Y")
                ),
                VehicleContractsModel.lease_end_date.return_variant(
                    raw_name="Fin", post_processing=DateConverter(date_format=r"%m/%d/%Y")
                ),
                VehicleContractsModel.update_date.return_variant(
                    raw_name="Date Prorogation", post_processing=DateConverter(date_format=r"%m/%d/%Y")
                ),
                VehicleContractsModel.lease_months.return_variant(
                    raw_name="Nbre mois", post_processing=lambda x: convert_numeric(x).round()
                ),
                VehicleContractsModel.lease_mileage.return_variant(
                    raw_name="Kms\ncontractuels", post_processing=lambda x: convert_numeric(x)
                ),
                VehicleContractsModel.lease_mileage_update.return_variant(
                    raw_name="Nvx kilométrages", post_processing=lambda x: convert_numeric(x).round()
                ),
                VehicleContractsModel.maintenance_rent_tax_exc.return_variant(
                    raw_name="Montant HT\nmaintenance/mois",
                ),
                VehicleContractsModel.financial_rent_tax_exc.return_variant(
                    raw_name="Montant loyer HT/mois", post_processing=lambda x: convert_numeric(x)
                ),
                MileageReportsModel.mileage.return_variant(
                    raw_name="Kilométrage relevé", post_processing=lambda x: convert_numeric(x)
                ),
                MileageReportsModel.mileage_date.return_variant(
                    raw_name="date relevé", post_processing=DateConverter(date_format=r"%m/%d/%Y")
                ),
                VehicleMaintenanceModel.computed_control_date.return_variant(
                    raw_name="Prochain CT avant", post_processing=DateConverter(date_format=r"%m/%d/%Y")
                ),
                VehicleContractsModel.contract_reference.return_variant(raw_name="N° Contrat"),
            ],
            record_dates=[VehicleContractsModel.lease_start_date.name],
            skip_cols=[
                "Agence",
                "Utilisateur",
                "Accessoires",
                "Conducteur",
                "Décision",
                "Kilométrage prévisionnel fin de contrat",
                "Nouveau Km contractuel",
                "Date application",
                "Nouveau loyer",
                "Régul loyer",
                "Nouvelle maintenance",
                "Régul maintenance",
                "Total régul HT",
                "Pneus 1er train",
                "Pneus 2e train",
                "Pneus 3e train",
                "Pneus 4e train",
                "Housses",
                "Housses ",
                "Assurance 2025(mois)",
                "Assurance 2024(mois)",
                "Unnamed: 36",
                "Unnamed: 31",
                "Unnamed: 24",
                "Unnamed: 19",
            ],
            skiprows=[0, 1, 2, 3],
            use_sheets=["Parc 2025"],
        )

        vehicle_df = vehicle_df[
            pd.notna(vehicle_df[VehiclesModel.plate_number.name])
            & pd.notna(vehicle_df[VehicleContractsModel.contract_type.name])
            & (vehicle_df[VehiclesModel.plate_number.name] != "N°Immatricul.")
        ]

        vehicle_df[VehicleContractsModel.contract_type.name] = mapper_factory(ContractType)(
            vehicle_df[VehicleContractsModel.contract_type.name]
        )
        vehicle_df[VehiclesModel.car_supplier.name] = mapper_factory(Suppliers)(
            vehicle_df[VehiclesModel.car_supplier.name]
        )

        # Update the lease dates and mileages
        vehicle_df[VehicleContractsModel.lease_end_date.name] = vehicle_df[
            VehicleContractsModel.lease_end_date.name
        ].mask(
            pd.notna(vehicle_df[VehicleContractsModel.update_date.name]),
            vehicle_df[VehicleContractsModel.update_date.name],
        )
        vehicle_df[VehicleContractsModel.lease_mileage.name] = vehicle_df[
            VehicleContractsModel.lease_mileage.name
        ].mask(
            pd.notna(vehicle_df[VehicleContractsModel.lease_mileage_update.name]),
            vehicle_df[VehicleContractsModel.lease_mileage_update.name],
        )

        vehicle_df[VehiclesModel.entry_into_fleet_date.name] = vehicle_df[VehicleContractsModel.lease_start_date.name]
        vehicle_df[VehiclesModel.exit_from_fleet_date.name] = vehicle_df[
            VehicleContractsModel.lease_end_date.name
        ].mask(vehicle_df[VehicleContractsModel.lease_end_date.name] > pd.Timestamp.now())

        # Override exit_from_fleet_date for some vehicles
        # on the "en circulation" side
        # despite their exit date
        vehicle_df[VehiclesModel.exit_from_fleet_date.name] = vehicle_df[VehiclesModel.exit_from_fleet_date.name].mask(
            vehicle_df[VehiclesModel.plate_number.name].isin(["BD-120-SA", "CR-737-WX", "DY-885-YH", "EN-873-JE"])
        )

        # Assign them to BC99 (c.f. email from Baptiste Brard 18/11/2025)
        vehicle_df[VehicleAssociationsModel.assigned_service.name] = "GROUPE > Direction - BC > BC99"
        vehicle_df[VehicleAssociationsModel.association_start_date.name] = vehicle_df[
            VehiclesModel.entry_into_fleet_date.name
        ]
        vehicle_df[VehicleAssociationsModel.association_end_date.name] = vehicle_df[
            VehiclesModel.exit_from_fleet_date.name
        ]

        # For these columns, 0 means unknown (hence null)
        for col in (
            VehicleContractsModel.lease_months.name,
            VehicleContractsModel.lease_mileage.name,
            VehicleContractsModel.maintenance_rent_tax_exc.name,
            VehicleContractsModel.financial_rent_tax_exc.name,
        ):
            vehicle_df[col] = vehicle_df[col].mask(vehicle_df[col] == 0)

        return vehicle_df


@attach_dataset(AcorusCsvUploadData)
class AcorusAssignmentSource(DataSource):
    NAME = "ASSIGNMENTS"

    def __fetch__(self: typing.Self) -> typing.Collection[str]:
        return (
            get_latest_file(
                target_folder=self.folder,
                pattern="^(?:ACORUS - voiture_sans_aen|acorus_vf_vs V2)\.xlsx$",
                s3_bucket=self.s3_bucket,
            ),
        )

    def __parse__(
        self: typing.Self,
        data_path: typing.Sequence[str],
        **parsing_params: typing.Dict[str, typing.Any],
    ) -> typing.Optional[pd.DataFrame]:
        if len(data_path) > 1:
            raise ValueError(f"Only one file path expected but {len(data_path)} passed")

        vehicle_df = self.load_table(
            file_path=data_path[0],
            col_lst=[
                VehiclesModel.plate_number.return_variant(
                    raw_name="Immatriculation",
                    post_processing=PlateConverter(
                        org_slug=self.organization_name,
                    ),
                ),
                VehicleAssociationsModel.assignment_type.return_variant(
                    raw_name="VS ou VF?",
                    post_processing=lambda x: x.map(
                        {
                            "VS": AssignmentType.service_vehicle.value,
                            "VF": AssignmentType.company_vehicle.value,
                        }
                    ),
                ),
            ],
            record_dates=[],
            skip_cols=[
                # Just interested in the assignment
                "Prénom dernier conducteur",
                "Nom dernier conducteur",
                "Statut parc",
                "Segment",
                "Modèle",
                "Premier mois sans AEN",
                "Dernier mois sans AEN",
                "Montant AEN déclaré 2024/2025",
                "Commentaire ACORUS",
                "Commentaire",
                "Catégorie de modèle",
                "Date d'entrée en parc",
                "Unnamed: 7",
                "Nombre de sièges",
                "Nom du dernier conducteur",
            ],
        )

        return vehicle_df


if __name__ == "__main__":
    AcorusCsvUploadData.local_test(
        organization_name="acorus",
    )
