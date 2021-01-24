# -*- coding: utf-8 -*-

from odoo import models, fields, api

class SaleOrderLine(models.Model):

    _inherit = 'sale.order.line'

    fixed_discount = fields.Float(string="Fixed Discount")

    @api.onchange('fixed_discount')
    def action_calculate_discount(self):
        if self.fixed_discount:
            self.discount = (self.fixed_discount / self.price_subtotal) * 100

    @api.onchange('discount')
    def action_calculate_fixed_discount(self):
        if self.discount:
            self.fixed_discount = (self.discount / 100) * self.price_subtotal