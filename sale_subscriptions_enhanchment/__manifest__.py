{
    'name': 'Sales Subscription Enhancment',
    'version': '13.0.1.0.0',
    'author': 'White-code (Zienab Abd El Nasser)',
    'category': 'Sale',
    'depends': [
        'sale_subscription',
    ],
    'data': [
        'data/ir_cron.xml',
        'views/sale_subscription_template.xml',
        'views/sale_subscription.xml'
    ],
    'installable': True,
    'auto_install': False,
}
