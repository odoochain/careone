#  -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
import logging
_logger = logging.getLogger(__name__)
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class ProductTemplate(models.Model):
	_inherit = 'product.template'

	def compute_discounted_pack_price(self):
		for product in self:
			product.has_discounted_amount = False
			product.pack_products_price = 0
			if product.is_pack:
				price = 0
				for prod in product.wk_product_pack:
					price = price + prod.product_id.lst_price * prod.product_quantity
				rem_price = price - product.lst_price
				product.pack_products_price = price
				if rem_price <= 0:
					product.has_discounted_amount = True

	is_pack = fields.Boolean(
		string='Is product pack')
	wk_product_pack = fields.One2many(
		comodel_name='product.pack', 
		inverse_name='wk_product_template', 
		string='Product pack', copy=True)
	pack_stock_management = fields.Selection(
		[('decrmnt_pack', 'Decrement Pack Only'),
		('decrmnt_products', 'Decrement Products Only'),
		('decrmnt_both', 'Decrement Both')], 
		string='Pack Stock Management', 
		default='decrmnt_products')

	has_discounted_amount = fields.Boolean(
		compute="compute_discounted_pack_price",
		string="Remaning price")
	pack_products_price = fields.Float(
		compute="compute_discounted_pack_price",
		string="Total Product Price")

	@api.onchange('pack_stock_management')
	def select_type_default_pack_mgmnt_onchange(self):
		pk_dec = self.pack_stock_management
		if pk_dec == 'decrmnt_products':
			self.type = 'service'
		elif pk_dec == 'decrmnt_both':
			self.type = 'product'
		#else:
		#    prd_type = 'consu'
		#self.type = prd_type

	@api.model
	def create(self, vals):
		if vals.get('is_pack'):
			if not vals.get('wk_product_pack'):
				raise ValidationError(
					'No products in this pack. Select atleast one product.')
		return super(ProductTemplate, self).create(vals)

	@api.onchange('type')
	def select_default_pack_mgmnt_onchange_type(self):
		if self.is_pack:
			prd_type = self.type
			if prd_type == 'service':
				self.pack_stock_management = 'decrmnt_products'
			elif prd_type == 'product':
				self.pack_stock_management = 'decrmnt_both'
			
class ProductProduct(models.Model):
	_inherit = "product.product"

	@api.onchange('pack_stock_management')
	def select_type_default_pack_mgmnt_onchange(self):
		pk_dec = self.pack_stock_management
		if pk_dec == 'decrmnt_products':
			prd_type = 'service'
		elif pk_dec == 'decrmnt_both':
			prd_type = 'product'
		else:
			prd_type = 'consu'
		self.type = prd_type


class ProductPack(models.Model):
	_name = 'product.pack'
	_description = 'Product Pack'

	product_id = fields.Many2one(
		comodel_name='product.product', string='Product', required=True)
	product_quantity = fields.Float(
		string='Quantity', required=True, default=1)
	wk_product_template = fields.Many2one(
		comodel_name='product.template', string='Product pack')
	wk_image = fields.Binary(
		related='product_id.image_512', string='Image', store=True)
	price = fields.Float(related='product_id.lst_price',
						 string='Product Price')
	uom_id = fields.Many2one(
		related='product_id.uom_id', string="Unit of Measure", readonly="1")
	name = fields.Char(related='product_id.name', readonly="1")


class SaleOrderLine(models.Model):
	_inherit = 'sale.order.line'

	def _action_launch_stock_rule(self, previous_product_uom_qty=False):
		"""
		Launch procurement group run method with required/custom fields genrated by a
		sale order line. procurement group will launch '_run_move', '_run_buy' or '_run_manufacture'
		depending on the sale order line product rule.
		"""
		ctx = dict(self._context or {})
		filteredObj = []
		errors = []
		if ctx.get('wk_skip'):
			filterIds = ctx.get('wk_skip')
			filteredObj = self.filtered(lambda obj : obj.id not in filterIds)
		else:
			filteredObj = self
		for line in filteredObj:
			procurements = []
			if line.product_id.is_pack:
				qty = 0.0
				for move in line.move_ids:
					qty += move.product_qty
				if not  line.order_id.procurement_group_id:
					line.order_id.procurement_group_id = self.env['procurement.group'].create({
						'name': line.order_id.name, 'move_type': line.order_id.picking_policy,
						'sale_id': line.order_id.id,
						'partner_id': line.order_id.partner_shipping_id.id,
					})
				values = line._prepare_procurement_values(group_id=line.order_id.procurement_group_id)
				line_uom = line.product_uom
				quant_uom = line.product_id.uom_id
				if line.product_id.pack_stock_management == 'decrmnt_both':
					product_qty = line.product_uom_qty - qty
					product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
					try:
						procurements.append(self.env['procurement.group'].Procurement(
								line.product_id, product_qty, procurement_uom,
								line.order_id.partner_shipping_id.property_stock_customer,
								line.name, line.order_id.name, line.order_id.company_id, values))
						if procurements:
							self.env['procurement.group'].run(procurements)
					except UserError as error:
						errors.append(error.name)

				if line.product_id.pack_stock_management != 'decrmnt_pack':
					for pack_obj in line.product_id.wk_product_pack:
						if pack_obj.product_id.type == 'service':
							continue
						product_qty = line.product_uom_qty * pack_obj.product_quantity
						product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
						try:
							procurements.append(self.env['procurement.group'].Procurement(
								pack_obj.product_id, product_qty, procurement_uom,
								line.order_id.partner_shipping_id.property_stock_customer,
								line.name, line.order_id.name, line.order_id.company_id, values))
							if procurements:
								self.env['procurement.group'].run(procurements)
						except UserError as error:
							errors.append(error.name)
		return super(SaleOrderLine, self)._action_launch_stock_rule()

	@api.onchange('product_uom_qty', 'product_uom', 'route_id')
	def _compute_is_mto(self):
		res = super(SaleOrderLine,self)._compute_is_mto()
		for product in self:
			product_obj = product.product_id
			if product.product_id.type == 'product':
				if product_obj.is_pack:
					warning_mess = {}
					for pack_product in product_obj.wk_product_pack:
						qty = product.product_uom_qty
						if qty * pack_product.product_quantity > pack_product.product_id.virtual_available:
							warning_mess = {
								'title': _('Not enough inventory!'),
								'message': ('You plan to sell %s quantities of the pack %s but you have only  %s quantities of the product %s available, and the total quantity to sell is  %s !!' % (qty, pack_product.product_id.name, pack_product.product_id.virtual_available, pack_product.product_id.name, qty * pack_product.product_quantity))
							}
							return {'warning': warning_mess}
		return res


