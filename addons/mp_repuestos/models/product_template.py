from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class ProductTemplate(models.Model):
    """Apply MP Repuestos defaults on products created from POS."""

    _inherit = "product.template"

    qty_available_manual = fields.Float(
        string="Cantidad en inventario",
        compute="_compute_qty_available_manual",
        inverse="_inverse_qty_available_manual",
        digits="Product Unit of Measure",
    )
    # Override account defaults to ensure new products never start with taxes linked.
    taxes_id = fields.Many2many(default=lambda self: self.env["account.tax"])
    supplier_taxes_id = fields.Many2many(default=lambda self: self.env["account.tax"])

    @api.model
    def _get_default_iva_zero_tax(self, company_id, tax_type):
        company = self.env["res.company"].browse(company_id) if company_id else self.env.company
        if not company:
            company = self.env.company

        tax_model = self.env["account.tax"]
        base_domain = [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", tax_type),
            ("amount", "=", 0),
        ]
        search_order = "sequence, id"

        tax_group_model = self.env["account.tax.group"]
        has_afip_code = "l10n_ar_vat_afip_code" in tax_group_model._fields
        candidate_domains = []
        if has_afip_code:
            candidate_domains.append(base_domain + [("tax_group_id.l10n_ar_vat_afip_code", "=", "0")])
            candidate_domains.append(
                base_domain + [("tax_group_id.l10n_ar_vat_afip_code", "in", ("1", "2", "3", "7"))]
            )

        candidate_domains.extend(
            [
                base_domain + [("tax_group_id.name", "ilike", "IVA 0%")],
                base_domain + [("name", "ilike", "IVA 0%")],
                base_domain + [("tax_group_id.name", "ilike", "IVA")],
                base_domain + [("name", "ilike", "IVA")],
                base_domain,
            ]
        )

        for domain in candidate_domains:
            tax = tax_model.search(domain, limit=1, order=search_order)
            if tax:
                return tax

        raise UserError(
            "No se encontró un impuesto IVA 0% para la compañía %s. Configure uno para continuar." % company.display_name
        )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)

        if "is_storable" in self._fields and "default_is_storable" not in self.env.context:
            defaults["is_storable"] = defaults.get("is_storable", True) or True

        company_id = self.env.context.get("force_company") or self.env.company.id

        if "taxes_id" in self._fields and "default_taxes_id" not in self.env.context:
            defaults["taxes_id"] = defaults.get("taxes_id") or [
                Command.set(self._get_default_iva_zero_tax(company_id, "sale").ids)
            ]

        if "supplier_taxes_id" in self._fields and "default_supplier_taxes_id" not in self.env.context:
            defaults["supplier_taxes_id"] = defaults.get("supplier_taxes_id") or [
                Command.set(self._get_default_iva_zero_tax(company_id, "purchase").ids)
            ]

        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id

            if ("taxes_id" not in vals or not vals.get("taxes_id")) and "default_taxes_id" not in self.env.context:
                vals["taxes_id"] = [Command.set(self._get_default_iva_zero_tax(company_id, "sale").ids)]

            if ("supplier_taxes_id" not in vals or not vals.get("supplier_taxes_id")) and "default_supplier_taxes_id" not in self.env.context:
                vals["supplier_taxes_id"] = [Command.set(self._get_default_iva_zero_tax(company_id, "purchase").ids)]
        return super().create(vals_list)

    def _compute_qty_available_manual(self):
        for template in self:
            template.qty_available_manual = template.qty_available

    def _inverse_qty_available_manual(self):
        StockChangeQty = self.env["stock.change.product.qty"]
        for template in self:
            if not template.product_variant_id:
                # Todavía no existe una variante (nuevo producto o sin guardar).
                continue

            if template.product_variant_count != 1:
                raise UserError(
                    "Solo se puede editar la cantidad cuando el producto tiene una única variante."
                )

            product = template.product_variant_id
            target_qty = template.qty_available_manual
            current_qty = product.qty_available
            if float_is_zero(
                target_qty - current_qty,
                precision_rounding=product.uom_id.rounding,
            ):
                continue

            wizard = StockChangeQty.create(
                {
                    "product_tmpl_id": template.id,
                    "product_id": product.id,
                    "new_quantity": target_qty,
                }
            )
            wizard.change_product_qty()
