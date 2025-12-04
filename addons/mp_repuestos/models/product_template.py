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
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)

        if "is_storable" in self._fields and "default_is_storable" not in self.env.context:
            defaults["is_storable"] = defaults.get("is_storable", True) or True

        if "taxes_id" in self._fields and "default_taxes_id" not in self.env.context:
            defaults["taxes_id"] = defaults.get("taxes_id") or [Command.clear()]

        if "supplier_taxes_id" in self._fields and "default_supplier_taxes_id" not in self.env.context:
            defaults["supplier_taxes_id"] = defaults.get("supplier_taxes_id") or [Command.clear()]

        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "taxes_id" not in vals and "default_taxes_id" not in self.env.context:
                vals["taxes_id"] = [Command.clear()]
            if "supplier_taxes_id" not in vals and "default_supplier_taxes_id" not in self.env.context:
                vals["supplier_taxes_id"] = [Command.clear()]
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
