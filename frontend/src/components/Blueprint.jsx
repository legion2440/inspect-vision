/** The wireframe frame of the design system: hairline box + registration marks. */
export default function Blueprint({ as: Tag = 'div', className = '', children, ...rest }) {
  return (
    <Tag className={'blueprint ' + className} {...rest}>
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      {children}
    </Tag>
  );
}
