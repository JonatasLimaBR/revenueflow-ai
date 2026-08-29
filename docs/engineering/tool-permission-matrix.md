# Tool Permission Matrix

| Agente | Read tools | Write tools | Proibido |
|---|---|---|---|
| Recommendation Agent | search_products, get_product_details, get_inventory, get_customer_sales_context | nenhuma | quote, order, payment, discount |
| Negotiation Agent | get_price, calculate_margin | propose_allowed_discount | set_discount, create_order |
| Checkout Agent | get_quote, get_inventory, get_price | create_quote, create_order, create_payment_sandbox | policy mutation |
| Opportunity Agent | customer/opportunity reads | create_opportunity | send_whatsapp_direct |
| Sales Supervisor | state + routing | nenhuma ação financeira direta | price/order/payment mutation |

## Regra
Permissão ausente não pode ser compensada por prompt.
